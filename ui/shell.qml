// shell.qml - mascot chat bubble
//
// Standalone Quickshell project, run by path next to (not inside) any shell config:
//   qs -p <repo>/ui
// MASCOT_CHAT_SOCKET overrides the socket path (dev: mascot-dev-chat.sock).
// mascotd starts the bubble itself with MASCOT_BUBBLE_MANAGED=1; such a bubble
// quits with the daemon instead of waiting for the next one.

import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root

    readonly property string socketPath: Quickshell.env("MASCOT_CHAT_SOCKET")
        || `${Quickshell.env("XDG_RUNTIME_DIR")}/mascotd-chat.sock`
    readonly property bool managed: Quickshell.env("MASCOT_BUBBLE_MANAGED") === "1"
    property bool wasConnected: false

    function handleLine(line: string): void {
        if (!line)
            return;

        let event;
        try {
            event = JSON.parse(line);
        } catch (e) {
            console.warn("mascot-bubble: invalid line from daemon:", e.message);
            return;
        }

        if (event.event === "tap")
            bubble.openFor(event);
        else if (event.event === "dragged")
            bubble.closeFor(event.mascot);
    }

    Socket {
        id: daemon

        path: root.socketPath
        connected: true

        parser: SplitParser {
            onRead: line => root.handleLine(line)
        }

        onConnectedChanged: {
            console.info("mascot-bubble:", connected ? "connected to" : "disconnected from", path);
            if (connected)
                root.wasConnected = true;
            else if (root.managed && root.wasConnected)
                quitTimer.start();
        }
    }

    // Hyprland 0.56 crashes when a layer surface holding the keyboard is
    // destroyed while still mapped (the process exiting with the bubble open),
    // so hide it first and give the compositor a moment to unmap it
    Timer {
        id: quitTimer

        interval: 100
        onRunningChanged: if (running) bubble.dismiss()
        onTriggered: Qt.quit()
    }

    // Started by hand, the daemon may start after us or be restarted; keep trying
    Timer {
        interval: 2000
        repeat: true
        running: !daemon.connected && !(root.managed && root.wasConnected)
        // Assigning true while already false is not a change, so toggle
        onTriggered: {
            daemon.connected = false;
            daemon.connected = true;
        }
    }

    Bubble {
        id: bubble

        onReleased: mascot => {
            daemon.write(JSON.stringify({ event: "close", mascot: mascot }) + "\n");
            daemon.flush();
        }
    }
}
