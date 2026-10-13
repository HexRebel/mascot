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

    function send(event: var): void {
        if (!daemon.connected)
            return;
        daemon.write(JSON.stringify(event) + "\n");
        daemon.flush();
    }

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
        else if (event.event === "prototypes")
            bubble.prototypesListed(event.names);
        else if (event.event === "swapped")
            bubble.swapped(event);
        else if (event.event === "swap_failed")
            bubble.swapFailed(event);
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
            else
                // The daemon went away or turned chat off (CHAT_ENABLED=false)
                bubble.dismiss();
        }
    }

    // Never exit with the bubble mapped: Hyprland 0.56 can crash when it goes
    // away (see Bubble.hiding). dismiss() unmaps after 100 ms; the daemon has
    // already turned sprite input off before closing the socket
    Timer {
        id: quitTimer

        interval: 400
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

        onHiding: root.send({ event: "hiding" })
        onHidden: root.send({ event: "hidden" })
        onReleased: mascot => root.send({ event: "close", mascot: mascot })
        onTalked: (mascot, active) => root.send({ event: "talking", mascot: mascot, active: active })
        onListRequested: root.send({ event: "list" })
        onSwapRequested: (mascot, prototype) => root.send({ event: "swap", mascot: mascot, prototype: prototype })
    }
}
