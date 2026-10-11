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

    function close(): void {
        chat.running = false;
        bubble.visible = false;
        if (bubble.event)
            bubble.released(bubble.event.mascot);
    }

    // aichat's REPL dot commands need a tty, so the bubble emulates the useful
    // ones with aichat's CLI flags. Kept across bubbles until changed
    property string model: ""
    property string role: ""
    property string session: ""

    readonly property string helpText: [
        ".info                  vis aichats indstillinger",
        ".models / .roles / .sessions   list dem",
        ".model <navn>          skift model (fx openrouter:…)",
        ".role <navn>           skift rolle",
        ".session <navn>        start/fortsæt en session med hukommelse",
        ".exit model|role|session   gå tilbage til standard",
        ".clear                 ryd boblen"
    ].join("\n")

    function flags(): var {
        let args = [];
        if (bubble.model)
            args.push("-m", bubble.model);
        if (bubble.role)
            args.push("-r", bubble.role);
        if (bubble.session)
            args.push("-s", bubble.session, "--save-session");
        return args;
    }

    // Runs CHAT_COMMAND with args appended; they are passed as "$@", never
    // parsed by the shell
    function run(args: var): void {
        // Without CHAT_COMMAND use the bubble's own aichat config: the main one
        // asks to confirm tool calls, which nobody can answer from here
        const command = bubble.event?.command || 'AICHAT_CONFIG_DIR="$HOME/.config/aichat-bubble" aichat';
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
                say(`${key}: ${bubble[key] || "standard"}`);
                return;
            }
        case ".exit":
            if (!["model", "role", "session"].includes(arg)) {
                say("brug .exit model, .exit role eller .exit session");
                return;
            }
            bubble[arg] = "";
            say(`${arg}: standard`);
            return;
        case ".clear":
            bubble.transcript = "";
            return;
        default:
            say(`ukendt kommando ${name} - prøv .help`);
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
            run(flags().concat("--", text)); // "--": a message may start with '-'
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
                bubble.errorText = chatErrors.text.trim() || `Kommandoen fejlede (exit ${exitCode})`;
        }
    }

    Shape {
        anchors.fill: parent
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
                    text: bubble.busy ? "…" : `Skriv til ${bubble.event?.prototype ?? "mascotten"}…  (.help)`
                    color: theme.muted
                    font: input.font
                }
            }
        }
    }
}
