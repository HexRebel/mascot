// Menu.qml - the menu a right click on a mascot opens, at the pointer
//
// Shown from the daemon's menu event (like a tap event, see src/chat.c, with
// "asleep" and "all_asleep"); the daemon holds the mascot until the bubble
// lets go. It takes no keyboard and closes when an item is picked, when the
// pointer leaves it, or after a few seconds if the pointer never comes to it.
// Opened from a key (`mascot menu`), it takes the keyboard instead (arrows,
// Enter, Esc) and stays until it is closed.

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

PanelWindow {
    id: menu

    property var event: null
    // The bubble's colours (pywal)
    property QtObject theme: null
    // The page shown: "main", "settings" (the mascot's chat: model, role,
    // session, tools), "quiet" (how long all mascots sleep), "swap" ("Change
    // mascot"), "models", "roles" or "sessions"
    property string page: "main"
    // The mascot's model and role in the bubble, see Bubble.choiceOf()
    property var choice: ({ model: "", role: "", noRole: false, session: "" })

    // The lists the pages pick from: asked for when the menu opens (the last
    // ones until the answers), so the window is big enough for them from the
    // start. Prototype names come from the daemon (listed()), models, roles
    // and sessions from aichat, as the bubble runs it (CHAT_COMMAND)
    property var names: []
    property var models: []
    property var roles: []
    property var sessions: []
    property bool waiting: false // for the daemon's names
    // The models that have answered in the bubble (Bubble.usedModels), also
    // ones aichat does not list
    property var usedModels: []
    // The models OpenRouter has now, by id (Bubble.openRouterModels): aichat's
    // list of them is old, and those that are gone answer with an error, so
    // they are left out. null: not known (yet, or no network)
    property var openRouterModels: null

    // aichat's models and the ones used, without those OpenRouter no longer has
    readonly property var shownModels: menu.models.concat(menu.usedModels.filter(m => !menu.models.includes(m)))
        .filter(m => !m.startsWith("openrouter:") || !menu.openRouterModels || menu.openRouterModels[m.slice(11)])

    // What an item asks for, for mascot (argument: the prototype for "swap",
    // the dot command for "command"), see shell.qml
    signal picked(string action, int mascot, string argument)
    // Closed with nothing picked (the pointer left it, or never came)
    signal dismissed(int mascot)
    // The daemon's list of prototypes, answered with listed()
    signal listRequested()
    // `mascot menu`: asks the daemon for the menu at a mascot (-1: the first)
    signal menuRequested(int mascot)
    // OpenRouter's models, see openRouterModels
    signal openRouterRequested()

    // Opened from a key: keyboard instead of pointer, see keyboard
    property bool fromKey: false
    property bool keyboard: false
    property int selected: -1 // the item the keyboard is on

    function toggle(mascot: int): void {
        if (menu.visible || firstLists.running) {
            menu.dismiss();
        } else {
            menu.fromKey = true;
            menu.menuRequested(mascot);
        }
    }

    function openFor(e: var, choice: var): void {
        menu.keyboard = menu.fromKey;
        menu.fromKey = false;
        menu.event = e;
        menu.choice = choice;
        menu.page = "main";
        menu.waiting = true;
        menu.listRequested();
        menu.openRouterRequested();
        const command = (e.command || "aichat") + " %s </dev/null";
        modelList.command = ["sh", "-c", command.replace("%s", "--list-models")];
        roleList.command = ["sh", "-c", command.replace("%s", "--list-roles")];
        sessionList.command = ["sh", "-c", command.replace("%s", "--list-sessions")];
        modelList.running = true;
        roleList.running = true;
        sessionList.running = true;
        // The first time, wait a moment for the lists rather than grow after
        if (menu.names.length && menu.models.length)
            menu.show();
        else
            firstLists.restart();
    }

    function show(): void {
        firstLists.stop();
        menu.gliding = false;
        menu.visible = true;
        menu.turned();
        if (menu.keyboard)
            keys.forceActiveFocus();
        Qt.callLater(() => menu.gliding = true);
    }

    // Shows a waiting menu once all its lists are there
    function arrived(): void {
        if (firstLists.running && !menu.waiting && !modelList.running && !roleList.running && !sessionList.running)
            menu.show();
    }

    Timer {
        id: firstLists
        interval: 300
        onTriggered: menu.show()
    }

    Process {
        id: modelList

        stdout: StdioCollector {
            onStreamFinished: {
                const models = this.text.split("\n").map(l => l.trim()).filter(l => l);
                // This computer's models first
                menu.models = models.filter(m => m.startsWith("ollama:"))
                    .concat(models.filter(m => !m.startsWith("ollama:")));
            }
        }
        onExited: menu.arrived()
    }

    Process {
        id: roleList

        stdout: StdioCollector {
            // Not aichat's own (%shell%, %code%, ...)
            onStreamFinished: menu.roles = this.text.split("\n").map(l => l.trim()).filter(l => l && !/^%.*%$/.test(l))
        }
        onExited: menu.arrived()
    }

    Process {
        id: sessionList

        stdout: StdioCollector {
            onStreamFinished: menu.sessions = this.text.split("\n").map(l => l.trim()).filter(l => l)
        }
        onExited: menu.arrived()
    }

    // A new page (or the menu just opened) may not be under the pointer: it
    // only closes once the pointer has been on it and left, or never comes.
    // Still on it, there is no hover change to say so
    function turned(): void {
        menu.entered = hover.hovered;
        leaving.stop();
        if (menu.entered || menu.keyboard)
            neverEntered.stop();
        else
            neverEntered.restart();
        scroller.contentY = 0;
        // The keyboard starts on the first thing to pick (not the heading)
        menu.selected = menu.keyboard ? Math.max(0, menu.items.findIndex(item => item.action)) : -1;
    }

    // The keyboard's way around: up and down, into a page or pick (Enter,
    // Right), back (Left, Backspace), close (Esc); also vim's j, k, l and h
    // (with or without Ctrl), as nothing is typed here
    function key(event: var): void {
        const k = event.key;
        const count = menu.items.length;
        // Past what cannot be picked (the "Mascot" heading, "…")
        const step = by => {
            let i = menu.selected;
            for (let n = 0; n < count; n++) {
                i = (i + by + count) % count;
                if (menu.items[i].action)
                    return i;
            }
            return menu.selected;
        };
        if (k === Qt.Key_Down || k === Qt.Key_Tab || k === Qt.Key_J)
            menu.selected = step(1);
        else if (k === Qt.Key_Up || k === Qt.Key_Backtab || k === Qt.Key_K)
            menu.selected = step(-1);
        else if (k === Qt.Key_Return || k === Qt.Key_Enter || k === Qt.Key_Space)
            menu.choose(menu.items[menu.selected] ?? {});
        else if (k === Qt.Key_Right || k === Qt.Key_L) {
            const item = menu.items[menu.selected];
            if (item?.action === "page" && item !== menu.items[0])
                menu.choose(item); // into a page, not back
        } else if (k === Qt.Key_Left || k === Qt.Key_H || k === Qt.Key_Backspace) {
            if (menu.page !== "main")
                menu.choose(menu.items[0]); // ‹ Back
        } else if (k === Qt.Key_Escape)
            menu.dismiss();
        else
            return;
        event.accepted = true;
        // Keep it in view on a long page
        const top = menu.selected * menu.itemHeight;
        if (top < scroller.contentY)
            scroller.contentY = top;
        else if (top + menu.itemHeight > scroller.contentY + scroller.height)
            scroller.contentY = top + menu.itemHeight - scroller.height;
    }

    function dismiss(): void {
        const mascot = menu.event?.mascot ?? -1;
        menu.close();
        menu.dismissed(mascot);
    }

    function close(): void {
        menu.visible = false;
        menu.keyboard = false;
        menu.page = "main";
        firstLists.stop();
        neverEntered.stop();
        leaving.stop();
    }

    function choose(item: var): void {
        if (item.action === "page") {
            menu.page = item.argument;
            menu.turned();
        } else if (item.action) {
            menu.pick(item.action, item.argument ?? "");
        }
    }

    function listed(list: var): void {
        menu.waiting = false;
        menu.names = list;
        menu.arrived();
    }

    // Whether the last pick was made from the keyboard, see shell.qml
    property bool lastKeyboard: false

    function pick(action: string, argument: string): void {
        const mascot = menu.event.mascot;
        menu.lastKeyboard = menu.keyboard;
        menu.close();
        menu.picked(action, mascot, argument);
    }

    readonly property var items: ({
        main: mainItems,
        settings: settingsItems,
        quiet: quietItems,
        swap: swapItems,
        models: modelItems,
        roles: roleItems,
        sessions: sessionItems
    })[menu.page] ?? mainItems

    readonly property var mainItems: {
        const e = menu.event;
        if (!e)
            return [];
        return [
            { label: "Mascot", heading: true },
            { label: "Settings ›", action: "page", argument: "settings" },
            e.asleep ? { label: "Wake up", action: "wake" } : { label: "Sleep", action: "sleep" },
            e.all_asleep ? { label: "Wake everyone", action: "wake_all" }
                : { label: "Quiet ›", action: "page", argument: "quiet" },
            { label: "Todo list", action: "todo" },
            { label: "Reminders", action: "reminders" },
            { label: "Help", action: "command", argument: ".help" },
            { label: "Send away", action: "dismiss" } // last, out of the way; the last mascot going stops Mascot
        ];
    }

    readonly property var settingsItems: [
        { label: "‹ Back", action: "page", argument: "main" },
        { label: "Change mascot ›", action: "page", argument: "swap" },
        { label: "Model ›", action: "page", argument: "models" },
        { label: "Role ›", action: "page", argument: "roles" },
        { label: "Session ›", action: "page", argument: "sessions" },
        { label: "Tools", action: "command", argument: ".tools" },
        { label: "Info", action: "command", argument: ".info" }
    ]

    // All mascots sleep for a while (do not disturb); "Set time…" opens the
    // bubble with .quiet typed, for a time of one's own (e.g. 2h or 19:30)
    readonly property var quietItems: [
        { label: "‹ Back", action: "page", argument: "main" },
        { label: "10 min", action: "nap", argument: "10" },
        { label: "30 min", action: "nap", argument: "30" },
        { label: "1 hour", action: "nap", argument: "60" },
        { label: "Set time…", action: "type", argument: ".quiet " }
    ]

    readonly property var swapItems: !menu.event ? []
        : [{ label: "‹ Back", action: "page", argument: "settings" }].concat(menu.names.length
            ? menu.names.filter(n => n.toLowerCase() !== menu.event.prototype.toLowerCase())
                .map(n => ({ label: n, action: "swap", argument: n }))
            : [{ label: "…", action: "" }])

    // Picking runs .model/.role in the bubble, as typing it would; "Other
    // model…" opens it with .model typed, for one that is not listed
    readonly property var modelItems: [
        { label: "‹ Back", action: "page", argument: "settings" },
        { label: "Default", action: "command", argument: ".exit model", checked: !menu.choice.model }
    ].concat(menu.shownModels.map(m => ({ label: m, action: "command", argument: `.model ${m}`,
                                        checked: m === menu.choice.model })),
             [{ label: "Other model…", action: "type",
                argument: menu.models.some(m => m.startsWith("openrouter:")) ? ".model openrouter:" : ".model " }])

    readonly property string currentRole: menu.choice.role || (menu.choice.noRole ? "" : menu.event?.role ?? "")
    readonly property var roleItems: [
        { label: "‹ Back", action: "page", argument: "settings" },
        { label: "No role", action: "command", argument: ".exit role", checked: !menu.currentRole }
    ].concat(menu.roles.map(r => ({ label: r, action: "command", argument: `.role ${r}`,
                                   checked: r === menu.currentRole })))

    // aichat's own sessions (.session; a new one is named in the bubble)
    readonly property var sessionItems: [
        { label: "‹ Back", action: "page", argument: "settings" },
        { label: "None", action: "command", argument: ".exit session", checked: !menu.choice.session }
    ].concat(menu.sessions.map(s => ({ label: s, action: "command", argument: `.session ${s}`,
                                      checked: s === menu.choice.session })))

    // Geometry: the box (as wide as its longest label, up to maxWidth) has a
    // corner just past the pointer, so the pointer starts inside it; a long
    // page scrolls. The window is as big as the biggest page and stays put
    // while the box glides between pages (a resized and moved window jumps),
    // and takes input only on the box (mask)
    readonly property int itemHeight: 28
    readonly property int maxRows: 12
    readonly property int maxWidth: 340
    readonly property int padding: 6
    readonly property int textMargin: 10
    readonly property int checkWidth: 18
    readonly property int edge: 8
    readonly property int overlap: 12

    function widthOf(list: var): int {
        const widest = Math.max(0, ...list.map(item => metrics.advanceWidth(item.label)));
        return Math.min(maxWidth, Math.ceil(widest) + 2 * (textMargin + padding) + checkWidth + 4);
    }

    function heightOf(list: var): int {
        return Math.min(list.length, maxRows) * itemHeight + 2 * padding;
    }

    readonly property int menuWidth: widthOf(items)
    readonly property int menuHeight: heightOf(items)
    readonly property var pages: [mainItems, settingsItems, quietItems, swapItems, modelItems, roleItems, sessionItems]
    readonly property int windowWidth: Math.max(...pages.map(p => widthOf(p)))
    readonly property int windowHeight: Math.max(...pages.map(p => heightOf(p)))

    FontMetrics {
        id: metrics
        font.pixelSize: 13
    }
    readonly property int surfaceWidth: event ? event.surface.width : 0
    readonly property int surfaceHeight: event ? event.surface.height : 0
    readonly property int posX: event
        ? Math.max(edge, Math.min(event.pointer.x - overlap, surfaceWidth - windowWidth - edge)) : 0
    // Above the pointer when there is no room below it (mascots sit on the floor):
    // then the box keeps to the window's bottom
    readonly property bool above: !!event && event.pointer.y - overlap + windowHeight + edge > surfaceHeight
    readonly property int posY: !event ? 0 : above
        ? Math.max(edge, event.pointer.y + overlap - windowHeight) : event.pointer.y - overlap

    // No glide when it opens
    property bool gliding: false

    visible: false
    screen: Quickshell.screens.find(s => s.name === menu.event?.output) ?? Quickshell.screens[0] ?? null
    color: "transparent"

    anchors {
        top: true
        left: true
    }
    margins {
        left: menu.posX
        top: menu.posY
    }
    exclusiveZone: 0
    implicitWidth: windowWidth
    implicitHeight: windowHeight
    mask: Region {
        item: box
    }

    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "mascot-menu"
    WlrLayershell.keyboardFocus: menu.keyboard ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

    Item {
        id: keys

        focus: menu.keyboard
        Keys.onPressed: event => menu.key(event)
    }

    // Closes when the pointer leaves (after it came in), or never comes
    property bool entered: false

    Timer {
        id: neverEntered
        interval: 4000
        onTriggered: menu.dismiss()
    }

    Timer {
        id: leaving
        interval: 800
        onTriggered: menu.dismiss()
    }

    Rectangle {
        id: box

        width: menu.menuWidth
        height: menu.menuHeight
        // At the pointer, also when the window was pushed in from an edge
        x: menu.event ? Math.max(0, Math.min(menu.event.pointer.x - menu.overlap - menu.posX, menu.windowWidth - width)) : 0
        y: menu.above ? menu.windowHeight - height : 0
        clip: true
        radius: 10
        color: Qt.alpha(menu.theme?.background ?? "#1e1e2e", 0.95)
        border.color: Qt.alpha(menu.theme?.accent ?? "#89b4fa", 0.8)
        border.width: 1.5

        Behavior on width {
            enabled: menu.gliding
            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }
        Behavior on height {
            enabled: menu.gliding
            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }
        Behavior on x {
            enabled: menu.gliding
            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }

        HoverHandler {
            id: hover

            onHoveredChanged: {
                if (hovered) {
                    menu.entered = true;
                    neverEntered.stop();
                    leaving.stop();
                } else if (menu.entered) {
                    leaving.restart();
                }
            }
        }

        Flickable {
            id: scroller

            x: menu.padding
            y: menu.padding
            width: parent.width - 2 * menu.padding
            height: parent.height - 2 * menu.padding
            contentHeight: column.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Column {
                id: column

                width: parent.width

                Repeater {
                    model: menu.items

                    Rectangle {
                        required property var modelData
                        required property int index

                        width: parent.width
                        height: menu.itemHeight
                        radius: 6
                        color: (area.containsMouse || index === menu.selected) && modelData.action
                            ? Qt.alpha(menu.theme?.accent ?? "#89b4fa", 0.25) : "transparent"

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            x: menu.textMargin
                            width: parent.width - 2 * menu.textMargin - menu.checkWidth
                            elide: Text.ElideRight
                            text: modelData.label
                            color: modelData.heading ? (menu.theme?.accent ?? "#89b4fa")
                                : modelData.action === "dismiss" ? (menu.theme?.muted ?? "#a6adc8")
                                : (menu.theme?.foreground ?? "#cdd6f4")
                            font.pixelSize: 13
                            font.bold: !!modelData.heading
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.right: parent.right
                            anchors.rightMargin: menu.textMargin
                            visible: !!modelData.checked
                            text: "✓"
                            color: menu.theme?.accent ?? "#89b4fa"
                            font.pixelSize: 13
                        }

                        MouseArea {
                            id: area

                            anchors.fill: parent
                            hoverEnabled: true
                            // One call: it may replace the items, this one too
                            onClicked: menu.choose(parent.modelData)
                        }
                    }
                }
            }
        }
    }
}
