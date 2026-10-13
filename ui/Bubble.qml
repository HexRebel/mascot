// Bubble.qml - speech bubble window shown next to a tapped mascot
//
// Positions itself from the daemon's tap event (all coordinates are local to
// the mascot's layer surface, logical px, top-referenced) and runs the
// event's "command" with the typed text appended as one argument.

import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

PanelWindow {
    id: bubble

    // Last tap event from the daemon, see src/chat.c
    property var event: null

    // The daemon keeps the mascot sitting until told the bubble is gone
    signal released(int mascot)
    // Sent before and after unmapping. Hyprland 0.56 crashes when the bubble
    // unmaps with the pointer over a sprite, so the daemon turns sprite input
    // off in between (see environment_suppress_sprite_input() in mascotd).
    // TODO: remove when hyprwm/Hyprland#16311 is in a release — verify with
    // scripts/hyprland-repro/ (with unmapTimer and hiddenTimer)
    signal hiding()
    signal hidden()
    property bool closing: false

    // .mascots asks the daemon for its prototypes; .mascot <name> swaps the
    // mascot for another one in the same spot (see chat_swap() in mascotd)
    signal listRequested()
    signal swapRequested(int mascot, string prototype)

    // The mascot plays its "Talk" behavior while a reply streams (not for dot commands)
    signal talked(int mascot, bool active)
    property bool replying: false
    readonly property bool talking: replying && chat.running && visible && !closing
    onTalkingChanged: if (bubble.event)
        bubble.talked(bubble.event.mascot, bubble.talking)
    property string transcript: ""
    property string errorText: ""
    readonly property bool busy: chat.running

    // Geometry
    readonly property int bodyWidth: 380
    readonly property int radius: 14
    readonly property int tailWidth: 22
    readonly property int tailHeight: 14
    readonly property int padding: 16
    readonly property int gap: 4 // between tail tip and sprite
    readonly property int edge: 8 // min distance to the surface edge
    readonly property real stroke: 1.5
    readonly property real inset: stroke / 2

    readonly property int bodyHeight: Math.min(content.implicitHeight + 2 * padding, 360)
    readonly property int totalHeight: bodyHeight + tailHeight

    // Point the tail aims at: top-centre of the sprite (falls back to the pointer)
    readonly property var target: {
        const e = bubble.event;
        if (!e)
            return { x: 0, top: 0, bottom: 0 };
        if (e.sprite)
            return { x: e.sprite.x + e.sprite.width / 2, top: e.sprite.y, bottom: e.sprite.y + e.sprite.height };
        return { x: e.pointer.x, top: e.pointer.y, bottom: e.pointer.y };
    }
    readonly property int surfaceWidth: event ? event.surface.width : 0

    // Not enough room above the mascot -> hang below it with the tail on top
    readonly property bool below: target.top - totalHeight - gap < edge
    readonly property int posX: Math.max(edge, Math.min(target.x - bodyWidth / 2, surfaceWidth - bodyWidth - edge))
    readonly property int posY: below ? target.bottom + gap : target.top - totalHeight - gap
    readonly property real tailX: Math.max(radius + tailWidth, Math.min(target.x - posX, bodyWidth - radius - tailWidth))

    // Body and tail as ONE path: two overlapping shapes show a seam with a
    // translucent fill
    function outline(): string {
        const w = bodyWidth, h = bodyHeight, r = radius, tw = tailWidth / 2, th = tailHeight;
        const p = inset, tx = tailX + p;
        if (!below) {
            return `M ${r + p} ${p} H ${w - r + p} A ${r} ${r} 0 0 1 ${w + p} ${r + p}`
                + ` V ${h - r + p} A ${r} ${r} 0 0 1 ${w - r + p} ${h + p}`
                + ` H ${tx + tw} L ${tx} ${h + th + p} L ${tx - tw} ${h + p}`
                + ` H ${r + p} A ${r} ${r} 0 0 1 ${p} ${h - r + p} V ${r + p} A ${r} ${r} 0 0 1 ${r + p} ${p} Z`;
        }
        const t = th + p;
        return `M ${r + p} ${t} H ${tx - tw} L ${tx} ${p} L ${tx + tw} ${t}`
            + ` H ${w - r + p} A ${r} ${r} 0 0 1 ${w + p} ${t + r}`
            + ` V ${t + h - r} A ${r} ${r} 0 0 1 ${w - r + p} ${t + h}`
            + ` H ${r + p} A ${r} ${r} 0 0 1 ${p} ${t + h - r} V ${t + r} A ${r} ${r} 0 0 1 ${r + p} ${t} Z`;
    }

    function openFor(e: var): void {
        // A tap that raced a close: stay mapped and give the sprites back
        if (unmapTimer.running) {
            unmapTimer.stop();
            bubble.closing = false;
            bubble.hidden();
        }

        // Double clicks arrive as two taps: keep the open conversation
        if (bubble.visible && bubble.event && bubble.event.mascot === e.mascot) {
            input.forceActiveFocus();
            return;
        }

        chat.running = false;
        bubble.event = e;
        bubble.transcript = "";
        bubble.errorText = "";
        input.text = "";
        bubble.visible = true;
        input.forceActiveFocus();
    }

    // The mascot was dragged away from under the bubble
    function closeFor(mascot: int): void {
        if (bubble.visible && bubble.event?.mascot === mascot)
            bubble.close();
    }

    function prototypesListed(names: var): void {
        if (bubble.visible)
            say(names.length ? names.join("\n") : "no mascots loaded");
    }

    // The daemon replaced our mascot; keep the conversation going with the new one
    function swapped(e: var): void {
        if (!bubble.event || bubble.event.mascot !== e.mascot)
            return;
        bubble.event = Object.assign({}, bubble.event, { mascot: e.to, prototype: e.prototype });
        say(`mascot: ${e.prototype}`);
    }

    function swapFailed(e: var): void {
        if (bubble.visible && bubble.event?.mascot === e.mascot)
            say(e.reason);
    }

    // Hides the bubble without releasing the mascot (the daemon may be gone).
    // Looks closed at once, but unmaps only once the daemon has had time to
    // turn sprite input off
    function dismiss(): void {
        chat.running = false;
        if (!bubble.visible || bubble.closing)
            return;
        bubble.closing = true;
        hiddenTimer.stop();
        bubble.hiding();
        unmapTimer.start();
    }

    Timer {
        id: unmapTimer

        interval: 100
        onTriggered: {
            bubble.visible = false;
            bubble.closing = false;
            hiddenTimer.start();
        }
    }

    // Lets the compositor finish the unmap before sprites take input again
    Timer {
        id: hiddenTimer

        interval: 250
        onTriggered: bubble.hidden()
    }

    function close(): void {
        bubble.dismiss();
        if (bubble.event)
            bubble.released(bubble.event.mascot);
    }

    // aichat's REPL dot commands need a tty, so the bubble emulates the useful
    // ones with aichat's CLI flags. Kept across bubbles until changed
    property string model: ""
    property string role: ""
    property string session: ""

    readonly property string helpText: [
        ".info                  show aichat's settings",
        ".models / .roles / .sessions   list them",
        ".model <name>          switch model (e.g. openrouter:…)",
        ".role <name>           switch role (instead of Mascot's prompt)",
        ".session <name>        start/continue a session with memory",
        ".exit model|role|session   go back to the default",
        ".mascots               list the mascots you have",
        ".mascot <name>         swap this mascot for another one",
        ".clear                 clear the bubble"
    ].join("\n")

    function flags(): var {
        let args = [];
        if (bubble.model)
            args.push("-m", bubble.model);
        if (bubble.role)
            args.push("-r", bubble.role);
        else if (bubble.prompt)
            args.push("--prompt", bubble.prompt.replace(/\{name\}/g, bubble.event?.prototype || "a desktop mascot"));
        if (bubble.session)
            args.push("-s", bubble.session, "--save-session");
        return args;
    }

    // Runs CHAT_COMMAND with args appended; they are passed as "$@", never
    // parsed by the shell
    function run(args: var, reply = false): void {
        bubble.replying = reply;
        const command = bubble.event?.command || 'aichat';
        // stdin must be closed: aichat reads a non-tty stdin as extra input and
        // waits forever on the open pipe Process gives it
        chat.command = ["sh", "-c", command + ' "$@" </dev/null', "mascot-bubble"].concat(args);
        chat.running = true;
    }

    function say(text: string): void {
        bubble.transcript += text + "\n";
    }

    function dotCommand(text: string): void {
        const [name, ...rest] = text.split(/\s+/);
        const arg = rest.join(" ");
        switch (name) {
        case ".help":
            say(helpText);
            return;
        case ".info":
            run(flags().concat("--info"));
            return;
        case ".models":
            run(["--list-models"]);
            return;
        case ".roles":
            run(["--list-roles"]);
            return;
        case ".sessions":
            run(["--list-sessions"]);
            return;
        case ".model":
        case ".role":
        case ".session":
            {
                const key = name.slice(1);
                if (arg)
                    bubble[key] = arg;
                say(`${key}: ${bubble[key] || "default"}`);
                return;
            }
        case ".exit":
            if (!["model", "role", "session"].includes(arg)) {
                say("use .exit model, .exit role or .exit session");
                return;
            }
            bubble[arg] = "";
            say(`${arg}: default`);
            return;
        case ".mascots":
            bubble.listRequested();
            return;
        case ".mascot":
            if (!arg)
                say(`mascot: ${bubble.event?.prototype} - .mascot <name> to swap, .mascots to list`);
            else if (arg.toLowerCase() === bubble.event?.prototype?.toLowerCase())
                say(`already ${bubble.event.prototype}`);
            else
                bubble.swapRequested(bubble.event.mascot, arg);
            return;
        case ".clear":
            bubble.transcript = "";
            return;
        default:
            say(`unknown command ${name} - try .help`);
            return;
        }
    }

    function send(): void {
        const text = input.text.trim();
        if (!text || bubble.busy)
            return;

        bubble.errorText = "";
        bubble.transcript += (bubble.transcript ? "\n\n" : "") + "› " + text + "\n";
        input.text = "";
        if (text.startsWith("."))
            dotCommand(text);
        else
            run(flags().concat("--", text), true); // "--": a message may start with '-'
    }

    visible: false
    screen: Quickshell.screens.find(s => s.name === bubble.event?.output) ?? Quickshell.screens[0] ?? null
    color: "transparent"

    anchors {
        top: true
        left: true
    }
    margins {
        left: bubble.posX
        top: bubble.posY
    }
    exclusiveZone: 0
    implicitWidth: bodyWidth + 2 * inset
    implicitHeight: totalHeight + 2 * inset

    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "mascot-bubble"
    // OnDemand only focuses on click; the bubble is short-lived and Esc closes it,
    // so take the keyboard while it is open and type straight away
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    // Colours from pywal (read only), with fallbacks if the cache is missing
    QtObject {
        id: theme

        property color background: "#1e1e2e"
        property color foreground: "#cdd6f4"
        property color accent: "#89b4fa"
        property color muted: "#a6adc8"

        function apply(json: string): void {
            let data;
            try {
                data = JSON.parse(json);
            } catch (e) {
                return; // half-written file, keep current colours
            }
            theme.background = data.special?.background ?? theme.background;
            theme.foreground = data.special?.foreground ?? theme.foreground;
            theme.accent = data.colors?.color4 ?? theme.accent;
            theme.muted = data.colors?.color8 ?? theme.muted;
        }
    }

    // Mascot's own system prompt, used unless a role is chosen with .role; {name}
    // is the mascot's name. A prompt.md in the data directory replaces the
    // bundled one (an empty one turns the prompt off). Read when the bubble starts
    readonly property string dataDir: Quickshell.env("MASCOT_DATA_DIR")
        || `${Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share"}/mascot`
    property var userPrompt: null // null: no prompt.md in dataDir
    property string bundledPrompt: ""
    readonly property string prompt: (userPrompt ?? bundledPrompt).trim()

    FileView {
        path: `${bubble.dataDir}/prompt.md`
        printErrors: false
        onLoaded: bubble.userPrompt = this.text()
    }

    FileView {
        path: Quickshell.shellPath("prompt.md")
        onLoaded: bubble.bundledPrompt = this.text()
    }

    FileView {
        path: `${Quickshell.env("HOME")}/.cache/wal/colors.json`
        watchChanges: true
        printErrors: false

        onLoaded: theme.apply(this.text())
        onFileChanged: this.reload()
    }

    Process {
        id: chat

        stdout: SplitParser {
            splitMarker: "" // stream: append chunks as they arrive
            onRead: data => bubble.transcript += data
        }
        stderr: StdioCollector {
            id: chatErrors
        }

        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                bubble.errorText = chatErrors.text.trim() || `The command failed (exit ${exitCode})`;
        }
    }

    Shape {
        anchors.fill: parent
        visible: !bubble.closing
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: Qt.alpha(theme.background, 0.92)
            strokeColor: Qt.alpha(theme.accent, 0.8)
            strokeWidth: bubble.stroke
            joinStyle: ShapePath.RoundJoin

            PathSvg {
                path: bubble.outline()
            }
        }
    }

    Column {
        id: content

        visible: !bubble.closing
        x: bubble.inset + bubble.padding
        y: bubble.inset + bubble.padding + (bubble.below ? bubble.tailHeight : 0)
        width: bubble.bodyWidth - 2 * bubble.padding
        spacing: 10

        Item {
            width: parent.width
            height: title.implicitHeight

            Text {
                id: title

                text: bubble.event?.prototype ?? ""
                color: theme.accent
                font.bold: true
                font.pixelSize: 14
            }

            Text {
                anchors.right: parent.right
                text: "×"
                color: closeArea.containsMouse ? theme.foreground : theme.muted
                font.pixelSize: 16

                MouseArea {
                    id: closeArea

                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    onClicked: bubble.close()
                }
            }
        }

        Flickable {
            id: scroller

            width: parent.width
            height: Math.min(log.implicitHeight, 220)
            visible: bubble.transcript !== ""
            contentHeight: log.implicitHeight
            clip: true

            Text {
                id: log

                width: scroller.width
                text: bubble.transcript
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: theme.foreground
                font.pixelSize: 13

                // Follow the streamed answer
                onImplicitHeightChanged: scroller.contentY = Math.max(0, implicitHeight - scroller.height)
            }
        }

        Text {
            width: parent.width
            visible: bubble.errorText !== ""
            text: bubble.errorText
            wrapMode: Text.Wrap
            color: "#f38ba8"
            font.pixelSize: 12
        }

        Rectangle {
            width: parent.width
            height: input.implicitHeight + 14
            radius: 8
            color: Qt.alpha(theme.foreground, 0.06)
            border.width: input.activeFocus ? 1 : 0
            border.color: Qt.alpha(theme.accent, 0.6)

            TextInput {
                id: input

                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                verticalAlignment: TextInput.AlignVCenter
                color: theme.foreground
                selectionColor: Qt.alpha(theme.accent, 0.4)
                font.pixelSize: 13
                clip: true
                readOnly: bubble.busy

                Keys.onReturnPressed: bubble.send()
                Keys.onEnterPressed: bubble.send()
                Keys.onEscapePressed: bubble.close()

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: !input.text
                    text: bubble.busy ? "…" : `Message ${bubble.event?.prototype ?? "the mascot"}…  (.help)`
                    color: theme.muted
                    font: input.font
                }
            }
        }
    }
}
