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

        if (event.event === "tap") {
            menu.close();
            bubble.openFor(event);
        } else if (event.event === "menu") {
            // The daemon holds this mascot now, not the one the bubble shows
            if (bubble.visible && bubble.event?.mascot !== event.mascot)
                bubble.dismiss();
            menu.openFor(event, bubble.choiceOf(event.mascot));
        } else if (event.event === "dragged") {
            // Only hidden until it is dropped: a window that unmaps while the
            // button is down makes Hyprland end the drag with a false release
            bubble.hideFor(event.mascot);
        } else if (event.event === "dropped") {
            bubble.dropped(event.mascot);
            bubble.closeFor(event.mascot);
            if (menu.event?.mascot === event.mascot)
                menu.close();
        } else if (event.event === "egg") {
            // Tapped quickly many times: the mascot shows its easter egg, without the bubble
            bubble.closeFor(event.mascot);
        } else if (event.event === "prototypes") {
            // Asked for by the menu's "Change mascot", or by .mascots
            if (menu.waiting)
                menu.listed(event.names);
            else
                bubble.prototypesListed(event.names);
        }
        else if (event.event === "swapped")
            bubble.swapped(event);
        else if (event.event === "swap_failed")
            bubble.swapFailed(event);
        else if (event.event === "toggle")
            bubble.toggle();
        else if (event.event === "menu_toggle")
            menu.toggle(bubble.event?.mascot ?? -1);
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
            if (connected) {
                root.wasConnected = true;
                return;
            }
            // The daemon went away or turned chat off (CHAT_ENABLED=false)
            bubble.dismiss();
            if (!root.wasConnected)
                return;
            bubble.forget();
            if (root.managed)
                Qt.quit();
        }
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

        onReleased: mascot => root.send({ event: "close", mascot: mascot })
        onTalked: (mascot, active) => root.send({ event: "talking", mascot: mascot, active: active })
        onToolUsed: (mascot, tool) => root.send({ event: "doing", mascot: mascot, tool: tool })
        onAnswerWaits: mascot => root.send({ event: "answered", mascot: mascot })
        onHeldAgain: mascot => root.send({ event: "hold", mascot: mascot })
        onListRequested: root.send({ event: "list" })
        onSwapRequested: (mascot, prototype) => root.send({ event: "swap", mascot: mascot, prototype: prototype })
        onOpenRequested: mascot => root.send({ event: "open", mascot: mascot })
        onRemarkRequested: mascot => root.send({ event: "remark", mascot: mascot })
    }

    // The menu's mascot sits while it is open; let go of it, unless the
    // bubble shows it (and keeps it sitting)
    function releaseMenu(mascot: int): void {
        if (!(bubble.visible && bubble.event?.mascot === mascot))
            root.send({ event: "close", mascot: mascot });
    }

    // The right-click menu
    Menu {
        id: menu

        theme: bubble.colors
        usedModels: bubble.usedModels
        sessionKinds: bubble.sessionKinds
        openRouterModels: bubble.openRouterModels
        sessionsDir: bubble.sessionsDir
        mascotAichatDir: bubble.chatSetup === "mascot" ? bubble.mascotAichatDir : ""
        onOpenRouterRequested: bubble.askOpenRouter(null)
        onListRequested: root.send({ event: "list" })
        onMenuRequested: mascot => root.send({ event: "menu", mascot: mascot })
        onDismissed: mascot => root.releaseMenu(mascot)
        onPicked: (action, mascot, argument) => {
            // What opens the bubble keeps the mascot sitting; the rest lets
            // go first (so "Sleep" lies down straight away). From a key, the
            // bubble keeps the keyboard too, as with `mascot chat`
            if (!["todo", "reminders", "command", "type"].includes(action))
                root.releaseMenu(mascot);
            else if (menu.lastKeyboard)
                bubble.fromKey = true;
            if (action === "sleep" || action === "wake")
                root.send({ event: action, mascot: mascot });
            else if (action === "stay")
                root.send({ event: "stay", mascot: mascot, active: argument === "true" });
            else if (action === "nap")
                root.send({ event: "sleep", minutes: Number(argument) });
            else if (action === "wake_all")
                root.send({ event: "wake", all: true });
            else if (action === "todo")
                bubble.openWith(mascot, ".todo");
            else if (action === "reminders")
                bubble.openWith(mascot, ".reminders");
            else if (action === "command")
                bubble.openWith(mascot, argument);
            else if (action === "type")
                bubble.openTyping(mascot, argument);
            else if (action === "swap")
                root.send({ event: "swap", mascot: mascot, prototype: argument });
            else if (action === "dismiss") {
                bubble.closeFor(mascot);
                root.send({ event: "dismiss", mascot: mascot });
            }
        }
    }
}
