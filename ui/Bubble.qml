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

    // .mascots asks the daemon for its prototypes; .mascot <name> swaps the
    // mascot for another one in the same spot (see chat_swap() in mascotd)
    signal listRequested()
    signal swapRequested(int mascot, string prototype)

    // `mascot chat` (e.g. on a key): asks the daemon to open the bubble at the
    // mascot talked to last (-1: none, the daemon picks the first one)
    signal openRequested(int mascot)

    // A reminder is due: asks the daemon to open the bubble without the keyboard
    // (a remark's tap, see remark()) at this mascot, or a random one if it is
    // gone (-1: none)
    signal remarkRequested(int mascot)

    // The mascot plays its "Talk" behavior while a reply streams (not for dot commands)
    signal talked(int mascot, bool active)
    // Closed while it answered, the mascot has written its answer: it plays its
    // Answered behaviour until it is clicked (see close())
    signal answerWaits(int mascot)
    // Dragging lets go of a mascot; one that waits with an answer is held again
    // when it is dropped (see dropped())
    signal heldAgain(int mascot)
    readonly property bool talking: visible && !!current?.job && current.replying
    onTalkingChanged: if (bubble.event)
        bubble.talked(bubble.event.mascot, bubble.talking)
    // While a tool runs for it, the mascot can show what it does (e.g. its
    // "Todo" behavior for the todo list), see doingOf(); "" when the answer starts
    signal toolUsed(int mascot, string tool)
    readonly property string toolPose: talking ? (current?.toolKind ?? "") : ""
    property string shownPose: ""
    onToolPoseChanged: {
        if (!bubble.event)
            return;
        // A short answer would end the "?" (Unsure), the joy of a todo done or the
        // tear of a failed answer at once:
        // they stay a few seconds, set again after the daemon has sat the mascot down
        // for the end of the answer
        if (bubble.lingers(bubble.shownPose) && !bubble.toolPose && !bubble.talking) {
            bubble.linger(bubble.shownPose);
        } else {
            lingerTimer.stop();
            bubble.toolUsed(bubble.event.mascot, bubble.toolPose);
        }
        bubble.shownPose = bubble.toolPose;
    }

    function lingers(pose: string): bool {
        return pose === "unsure" || pose === "done" || pose === "failed" || pose === "fullpower";
    }

    function linger(pose: string): void {
        const mascot = bubble.event.mascot;
        Qt.callLater(() => bubble.toolUsed(mascot, pose));
        lingerTimer.restart();
    }

    Timer {
        id: lingerTimer

        interval: 5000
        onTriggered: if (bubble.event)
            bubble.toolUsed(bubble.event.mascot, bubble.toolPose)
    }

    // Each mascot keeps its own conversation until the bubble quits (with the
    // daemon), by mascot id, and a reply keeps streaming into it while the
    // bubble is closed or shows another mascot. The aichat sessions that give
    // the model its memory live in the runtime dir and are removed when the
    // bubble starts and quits, never in aichat's own sessions dir
    property var conversations: ({})
    property QtObject current: null // the conversation shown
    readonly property var entries: current ? current.entries : null
    readonly property bool busy: !!current?.job
    property int memoryCount: 0
    readonly property string memoryDir: `${Quickshell.env("XDG_RUNTIME_DIR")}/mascot-memory/`
        + (Quickshell.env("MASCOT_CHAT_SOCKET") || "mascotd-chat").replace(/^.*\//, "").replace(/\.sock$/, "")

    Component.onCompleted: Quickshell.execDetached(["rm", "-rf", "--", bubble.memoryDir])

    Component {
        id: conversationComponent

        QtObject {
            // One entry per message: kind is "you" (typed by the user), "reply"
            // (the model's answer), "remark" (what the mascot said on its own),
            // "reminder" (one that is due), "listing" (a tree a tool drew, in a
            // fixed-width font) or "system" (the bubble's own notes and dot
            // command output), each drawn in its own pywal colour
            property ListModel entries: ListModel {}
            property int streaming: -1 // entry the running command writes into
            property int readFrom: -1 // the latest dot command's line: its output is read from the top
            property var job: null // the running command, see run()
            property bool replying: false // job answers a message, not a dot command
            property string doing: "" // what a tool is doing while it waits, see doingOf()
            property string doingIcon: "" // its icon's name, see icon()
            property string toolKind: "" // doingIcon from when the tool starts until the answer does
            // check_system/read_log came back empty-handed, and none found anything:
            // the mascot shows it does not know ("unsure") while it answers
            property bool unsure: false
            property bool found: false
            property bool ticked: false // remove_todo took an item off: the mascot is glad ("done")
            property bool fullPower: false // check_system saw the CPU set to performance ("fullpower")
            property int mascot: -1 // whose conversation it is
            // Closed while answering: the mascot stays sitting (and talking)
            // until the answer is read, see close()
            property bool waiting: false
            property int waits: 0 // which close() a timer belongs to
            property string error: ""
            property string memory: "" // the aichat session that remembers it
            property string persona: "" // the role flags that session started with
            property int memoryChars: 0 // roughly what that session holds, see ask()
            // .model/.role/.session for this mascot only; see dotCommand()
            property string model: ""
            property string role: "" // empty: the daemon's role for it (event.role), else Mascot's prompt
            property bool noRole: false // .exit role: no role at all, not even the daemon's
            property string session: ""
        }
    }

    function conversation(mascot: int): QtObject {
        if (!bubble.conversations[mascot])
            bubble.conversations[mascot] = conversationComponent.createObject(bubble, { mascot: mascot });
        return bubble.conversations[mascot];
    }

    // Stops a conversation's running command; what it wrote so far stays
    function stop(c: QtObject): void {
        if (!c?.job)
            return;
        const job = c.job;
        c.job = null;
        job.running = false;
    }

    // Drops every conversation, e.g. when the daemon goes away (a new one
    // starts counting mascot ids from 0 again)
    function forget(): void {
        bubble.event = null;
        bubble.current = null;
        for (const mascot in bubble.conversations) {
            stop(bubble.conversations[mascot]);
            bubble.conversations[mascot].destroy();
        }
        bubble.conversations = {};
        bubble.lookups = {};
        bubble.contexts = {};
        Quickshell.execDetached(["rm", "-rf", "--", bubble.memoryDir]);
    }

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

    readonly property int maxBodyHeight: 360
    readonly property int bodyHeight: Math.min(content.implicitHeight + 2 * padding, maxBodyHeight)
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

    property real tappedAt: 0 // the last tap's time, see openFor()

    function openFor(e: var): void {
        if (e.remark) {
            bubble.remark(e);
            return;
        }
        bubble.remarking = false;
        bubble.reminding = false;
        bubble.keepKeyboard = bubble.fromKey;
        bubble.fromKey = false;
        // Double clicks arrive as two taps: keep the open conversation. Taken again
        // only after a while: while it is Exclusive Hyprland gives it the pointer too,
        // and quick taps (the easter egg) would miss the mascot every other time
        const quick = Date.now() - bubble.tappedAt < 1000;
        bubble.tappedAt = Date.now();
        if (bubble.visible && bubble.event && bubble.event.mascot === e.mascot) {
            if (!quick)
                bubble.grabKeyboard();
            input.forceActiveFocus();
            runPending();
            return;
        }

        bubble.event = e;
        bubble.current = conversation(e.mascot);
        bubble.current.waiting = false;
        input.text = "";
        bubble.grabKeyboard(); // before showing it, so it maps with the keyboard
        bubble.visible = true;
        input.forceActiveFocus();
        warmUp(bubble.current, bubble.event?.command || "aichat"); // while the first message is written
        runPending();
    }

    // The menu's "Todo list", "Reminders" and "Info": open the bubble at the mascot
    // (the daemon answers with a tap, see openFor()) and run the dot command there
    property string pendingCommand: ""

    function openWith(mascot: int, command: string): void {
        bubble.pendingCommand = command;
        bubble.openRequested(mascot);
    }

    // The menu's "Set time…": open the bubble with the start of a dot command
    // typed (".quiet "), for the rest to be written
    property string pendingText: ""

    function openTyping(mascot: int, text: string): void {
        bubble.pendingText = text;
        bubble.openRequested(mascot);
    }

    function runPending(): void {
        if (bubble.pendingText) {
            input.text = bubble.pendingText;
            input.cursorPosition = input.text.length;
            bubble.pendingText = "";
        }
        const command = bubble.pendingCommand;
        bubble.pendingCommand = "";
        if (!command || bubble.busy)
            return;
        bubble.entries.append({ kind: "you", body: command });
        dotCommand(command);
    }

    // CHAT_REMARKS: the mascot says something on its own. The bubble opens
    // without the keyboard (Hyprland gives an OnDemand layer surface the
    // keyboard when it maps, so it has none) and closes 7 s after the remark is
    // written, unless the pointer is on it; a click makes it a normal chat
    property bool remarking: false

    function remark(e: var): void {
        // Asked for to show reminders that are due
        if (bubble.awaitingTap) {
            bubble.awaitingTap = false;
            const due = dueReminders();
            if (bubble.visible || !due.length) {
                if (due.length)
                    showReminders(due, bubble.current);
                if (bubble.event?.mascot !== e.mascot || !bubble.visible)
                    bubble.released(e.mascot);
                return;
            }
            bubble.event = e;
            bubble.current = conversation(e.mascot);
            input.text = "";
            bubble.remarking = true;
            bubble.reminding = true;
            bubble.visible = true;
            showReminders(due, bubble.current);
            return;
        }
        const c = conversation(e.mascot);
        // Shown already or still answering: the daemon can let the mascot go
        if (bubble.visible || c.job) {
            bubble.released(e.mascot);
            return;
        }
        bubble.event = e;
        bubble.current = c;
        input.text = "";
        bubble.remarking = true;
        bubble.visible = true;
        // Not shown, but kept in the memory like any message
        ask("(Not from the user: you have not talked for a while. Say one short "
            + "thing to the user on your own, in character - a remark, a question or something you noticed. "
            + "Write in the language of your earlier conversation, if any, else in "
            + `${bubble.language}. Do not mention this note.)`, "remark");
    }

    // Reminders (.remind, the reminders tool): reminderFile is watched, and each
    // reminder is shown when it is due - in the open bubble, or else the bubble
    // opens at a mascot like a remark, but stays until closed. One that fell due
    // while Mascot was not running is shown when it starts again. Once shown,
    // due_reminders takes them off the file
    property bool reminding: false // the bubble opened for reminders: no closing by itself
    property var reminders: [] // { at: ms, text }, from reminderFile
    property real shownUntil: 0 // reminders due by then are shown (and being taken off)
    property bool awaitingTap: false // asked the daemon for a remark's tap to show them
    property real awaitingSince: 0

    function parseReminders(text: string): var {
        const list = [];
        for (const line of text.split("\n")) {
            const m = line.match(/^- (\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d)(?::(\d\d))? (.*\S)\s*$/);
            if (m)
                list.push({ at: new Date(+m[1], m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0)).getTime(), text: m[7] });
        }
        return list.sort((a, b) => a.at - b.at);
    }

    function dueReminders(): var {
        const now = Date.now();
        return bubble.reminders.filter(r => r.at <= now && r.at > bubble.shownUntil);
    }

    function checkReminders(): void {
        const due = dueReminders();
        if (!due.length)
            return;
        if (bubble.visible && bubble.current) {
            showReminders(due, bubble.current);
            return;
        }
        // The daemon gives no tap while a mascot is held, off the floor (falling
        // after Mascot starts) or there is none: try again
        if (bubble.awaitingTap && Date.now() - bubble.awaitingSince < 5000)
            return;
        bubble.awaitingTap = true;
        bubble.awaitingSince = Date.now();
        bubble.remarkRequested(bubble.event?.mascot ?? -1); // the one talked to last
    }

    function showReminders(due: var, c: QtObject): void {
        const now = Date.now();
        for (const r of due) {
            // Late (Mascot was not running): say when it was for
            const late = now - r.at > 60000 ? ` (was for ${Qt.formatDateTime(new Date(r.at), "ddd dd.MM HH:mm")})` : "";
            c.entries.append({ kind: "reminder", body: `⏰ ${r.text}${late}` });
        }
        // The mascot shows it is time (its "Alarm" behavior): until the bubble that
        // opened for it closes, or for a few seconds in a conversation
        if (bubble.visible && bubble.event && c === bubble.current) {
            bubble.toolUsed(bubble.event.mascot, "alarm");
            if (bubble.reminding)
                alarmTimer.stop();
            else
                alarmTimer.restart();
        }
        bubble.shownUntil = Math.max(bubble.shownUntil, ...due.map(r => r.at));
        // Through env, not the Process's environment: Quickshell 0.3.0 (Debian 13)
        // cannot bind an object to it, and the tool would refuse to run
        dueJob.command = ["env", "MASCOT_TOOLS_LOCAL=1", `MASCOT_REMINDER_FILE=${bubble.reminderFile}`,
            `${bubble.toolsDir}/bin/due_reminders`, JSON.stringify({ until: bubble.shownUntil / 1000 })];
        dueJob.running = true;
    }

    Timer {
        id: alarmTimer

        interval: 6000
        onTriggered: if (bubble.event)
            bubble.toolUsed(bubble.event.mascot, bubble.toolPose)
    }

    FileView {
        id: reminderView

        path: bubble.reminderFile
        watchChanges: true
        printErrors: false
        onLoaded: bubble.reminders = bubble.parseReminders(this.text())
        onLoadFailed: bubble.reminders = []
        onFileChanged: this.reload()
    }

    Process {
        id: dueJob

        onExited: reminderView.reload()
    }

    Timer {
        interval: 5000
        repeat: true
        running: bubble.reminders.length > 0
        triggeredOnStart: true
        onTriggered: bubble.checkReminders()
    }

    Timer {
        interval: 7000
        running: bubble.remarking && !bubble.reminding && bubble.visible && !bubble.busy && !remarkHover.hovered
        onTriggered: bubble.close()
    }

    // Take the keyboard briefly, then let go to OnDemand, so a click elsewhere
    // (e.g. a terminal) can take it while the bubble stays open
    property bool grabbing: false

    function grabKeyboard(): void {
        bubble.grabbing = true;
        releaseGrab.restart();
    }

    Timer {
        id: releaseGrab
        interval: 300
        onTriggered: bubble.grabbing = false
    }

    // `mascot chat`: close the bubble, or open it again at the last mascot (the
    // daemon answers with a tap event, see openFor())
    function toggle(): void {
        if (bubble.visible) {
            bubble.close();
        } else {
            bubble.fromKey = true;
            bubble.openRequested(bubble.event?.mascot ?? -1);
        }
    }

    // Opened from a key (`mascot chat`): the pointer is elsewhere, and Hyprland
    // hands the keyboard back to the window under it once the bubble drops to
    // OnDemand, so such a bubble keeps the keyboard until it closes
    property bool fromKey: false
    property bool keepKeyboard: false

    // The mascot is being dragged away from under the bubble: invisible (but
    // still mapped, see shell.qml) until it is dropped, then closeFor()
    property bool hiddenForDrag: false

    function hideFor(mascot: int): void {
        if (bubble.visible && bubble.event?.mascot === mascot)
            bubble.hiddenForDrag = true;
    }

    // A mascot waiting with its answer was dragged: hold it again, so it goes
    // on talking, or shows it has answered (NEW), once it lands
    function dropped(mascot: int): void {
        const c = bubble.conversations[mascot];
        // Open at another mascot: that one is held now (only one is)
        if (!c?.waiting || bubble.visible)
            return;
        bubble.heldAgain(mascot);
        if (c.job)
            bubble.talked(mascot, true);
        else
            bubble.answerWaits(mascot);
    }

    function closeFor(mascot: int): void {
        if (bubble.visible && bubble.event?.mascot === mascot)
            bubble.close(false); // dragged: the daemon has let go of it already
    }

    function prototypesListed(names: var): void {
        if (bubble.visible)
            say(names.length ? names.join("\n") : "no mascots loaded");
    }

    // The daemon replaced our mascot; keep the conversation going with the new one
    function swapped(e: var): void {
        if (!bubble.event || bubble.event.mascot !== e.mascot)
            return;
        bubble.conversations[e.to] = conversation(e.mascot);
        bubble.conversations[e.to].mascot = e.to;
        delete bubble.conversations[e.mascot];
        // Older daemons send no role with it: keep the old one
        bubble.event = Object.assign({}, bubble.event, { mascot: e.to, prototype: e.prototype },
                                     "role" in e ? { role: e.role } : {});
        say(`mascot: ${e.prototype}`);
    }

    function swapFailed(e: var): void {
        if (bubble.visible && bubble.event?.mascot === e.mascot)
            say(e.reason);
    }

    // Hides the bubble without releasing the mascot (the daemon may be gone); a
    // running reply carries on into its conversation
    function dismiss(): void {
        bubble.visible = false;
        bubble.hiddenForDrag = false;
        coolDown();
        bubble.remarking = false; // after hiding, or OnDemand would take the keyboard first
        bubble.reminding = false;
        bubble.keepKeyboard = false;
    }

    // Closed while the mascot answers (not dragged away): it keeps sitting and
    // talking until the answer is written, then shows that it has answered and
    // waits there to be clicked (see answered()) - at most 10 minutes
    function close(waitForAnswer = true): void {
        const c = bubble.current;
        const wait = waitForAnswer && !!c?.job && c.replying && !!bubble.event && !bubble.remarking;
        bubble.dismiss();
        if (!bubble.event)
            return;
        if (!wait) {
            bubble.released(bubble.event.mascot);
            return;
        }
        c.waiting = true;
        const token = ++c.waits;
        bubble.talked(c.mascot, true);
        after(10 * 60 * 1000, () => {
            if (c.waiting && c.waits === token) {
                c.waiting = false;
                bubble.released(c.mascot);
            }
        });
    }

    // A waiting mascot's answer is written: "I have answered"
    function answered(c: QtObject): void {
        if (c.waiting)
            bubble.answerWaits(c.mascot);
    }

    function after(ms: int, done: var): void {
        const timer = Qt.createQmlObject("import QtQuick; Timer {}", bubble);
        timer.interval = ms;
        timer.triggered.connect(() => {
            timer.destroy();
            done();
        });
        timer.start();
    }

    // aichat's REPL dot commands need a tty, so the bubble emulates the useful
    // ones with aichat's CLI flags. .model, .role and .session apply to this
    // mascot's conversation until changed
    function chosen(): QtObject {
        return bubble.current;
    }

    // A mascot's .model, .role and .session, for the menu (Menu.qml)
    function choiceOf(mascot: int): var {
        const c = bubble.conversations[mascot];
        return { model: c?.model ?? "", role: c?.role ?? "", noRole: c?.noRole ?? false, session: c?.session ?? "" };
    }

    // .help: what most people need; .help all: every command
    readonly property string helpShort: [
        "Just write to me, or use a command:",
        ".model <name>          switch model (.models lists them)",
        ".todo                  your todo list (.todo add <item>)",
        ".remind <when> <text>  a reminder, e.g. .remind 10m tea",
        ".quiet <when>          let the mascots sleep, e.g. .quiet 2h",
        ".copy                  copy the last answer",
        ".clear                 start this conversation over",
        ".help all              every command",
        "",
        "Right-click a mascot for its menu. Select text and press Ctrl+C to copy it."
    ].join("\n")
    readonly property string helpText: [
        ".info                  show Mascot's version and aichat's settings",
        ".models / .roles / .sessions   list them",
        ".models <search>       find models on OpenRouter, e.g. .models gemini",
        ".model <name>          switch model (e.g. openrouter:…)",
        ".role <name>           switch role (instead of the default)",
        ".session <name>        start/continue a session with memory",
        ".delete session <name> delete a session for good",
        ".exit model|session    go back to the default",
        ".exit role             leave the role (also the default one)",
        ".mascots               list the mascots you have",
        ".mascot <name>         swap this mascot for another one",
        ".tools                 list what the mascot can look up",
        ".todo                  show the todo list",
        ".todo add <item>       add to it",
        ".todo done <n|text>    remove items (by number or text, e.g. 1, 4)",
        ".todo edit <n> <text>  change what an item says",
        ".remind <when> <text>  set a reminder, e.g. .remind 10m tea",
        ".reminders             list them",
        ".remind cancel <n|text>  cancel one",
        ".quiet <when>          all mascots sleep until then, e.g. .quiet 2h",
        ".quiet now             wake them up again",
        ".copy                  copy the last answer",
        ".clear                 start this conversation over",
        "",
        "Select text with the mouse and press Ctrl+C to copy part of it."
    ].join("\n")

    // The user's language for remarks: CHAT_LANGUAGE, else the locale's language
    // by name ("English" for en_DK: its code alone made models guess Norwegian)
    readonly property string language: bubble.event?.language || Qt.locale().nativeLanguageName || Qt.locale().name

    function roleFlags(): var {
        const c = chosen();
        const role = c.role || (c.noRole ? "" : bubble.event.role);
        if (role)
            return ["-r", role]; // only ever one -r: aichat refuses two
        if (bubble.prompt)
            return ["--prompt", bubble.prompt.replace(/\{name\}/g, bubble.event?.prototype || "a desktop mascot")
                + (bubble.event?.language ? `\n\nThe user's language is ${bubble.event.language}: answer in it unless the user writes in another language.` : "")];
        return [];
    }

    function flags(): var {
        const c = chosen();
        let args = (c.model ? ["-m", c.model] : []).concat(roleFlags());
        if (c.session)
            args.push("-s", c.session, "--save-session");
        return args;
    }

    // A memory holds about this many characters before ask() sums it up into
    // a fresh one: CHAT_MEMORY tokens (the tap event's "memory", 0 = never) at
    // 3 characters each, a cautious guess for most languages; 8000 tokens if
    // the daemon is older. MASCOT_MEMORY_LIMIT (characters) overrides it, for
    // testing. With a local model, at most half its context (see memoryFor())
    readonly property int memoryLimit: parseInt(Quickshell.env("MASCOT_MEMORY_LIMIT"))
        || (bubble.event?.memory === 0 ? 0 : (bubble.event?.memory ?? 8000) * 3)

    // memoryLimit for this conversation's model: done(characters, why). Ollama
    // cuts the start of a conversation that outgrows the context off silently,
    // and the start is the prompt - the mascot would forget who it is; a model
    // online refuses it. So the memory is at most half the model's context,
    // leaving room for the prompt, a file a tool reads and the answer. It never
    // grows past CHAT_MEMORY, though, not even for a big model online: the
    // whole memory goes with every message, and online each token is paid for
    function memoryFor(c: QtObject, command: string, done: var): void {
        if (Quickshell.env("MASCOT_MEMORY_LIMIT")) {
            done(bubble.memoryLimit, "MASCOT_MEMORY_LIMIT");
            return;
        }
        if (!bubble.memoryLimit) {
            done(0, "CHAT_MEMORY=0");
            return;
        }
        const cap = tokens => tokens > 0 && tokens / 2 * 3 < bubble.memoryLimit
            ? done(tokens / 2 * 3, "half the model's context") : done(bubble.memoryLimit, "CHAT_MEMORY");
        // The same probe as withTools(), so aichat is asked once
        const probe = (c.model ? ["-m", c.model] : []).concat(roleFlags(), "-s", "mascot-probe");
        lookup(probe, c, command, (info, ok) => {
            const model = ok ? (info.match(/^model:?\s+(\S+)/m) ?? [])[1] ?? "" : "";
            const local = model.match(/^ollama:(\S+)/);
            if (!local) {
                // OpenRouter says how big its models are; of others it is not known
                if (!model.startsWith("openrouter:")) {
                    done(bubble.memoryLimit, "CHAT_MEMORY");
                    return;
                }
                bubble.askOpenRouter(known => cap(known
                    ? bubble.openRouterList.find(m => m.id === model.slice(11))?.context_length ?? 0 : 0));
                return;
            }
            if (local[1] in bubble.contexts) {
                cap(bubble.contexts[local[1]]);
                return;
            }
            const path = `${bubble.toolsDir}/bin/context_size`.replace(/'/g, "'\\''");
            run(["{}"], false, "", (out, ok) => {
                bubble.contexts[local[1]] = ok ? parseInt(out) || 0 : 0;
                cap(bubble.contexts[local[1]]);
            }, c, `'${path}'`, { MASCOT_TOOLS_LOCAL: "1", MASCOT_VISION_MODEL: local[1] });
        });
    }

    // The context of each local model (tokens, 0: unknown), from context_size
    property var contexts: ({})

    // CHAT_TOOLS (the tap event's "tools"): the tools in ../tools the model may
    // use, by the names CHAT_TOOLS knows them by ("time" needs none: every
    // message starts with the date and time, see ask()). They only read, but for
    // the todo list (todoFile, also .todo). The bubble always
    // points aichat at those, never at your own llm-functions, and turns
    // function calling off without them, so no tool of yours can write or run
    // anything unconfirmed from the bubble
    readonly property var toolFunctions: ({
        time: [],
        weather: ["get_current_weather"],
        files: ["list_directory", "read_file", "search_file", "look_at_image"],
        todo: ["list_todos", "add_todo", "remove_todo", "edit_todo"],
        reminders: ["set_reminder", "list_reminders", "cancel_reminder"],
        shell: ["last_commands"],
        sleep: ["sleep_mode"],
        system: ["check_system", "read_log"]
    })
    // Only with a local model, so what they read stays on this computer
    readonly property var localTools: ["files", "todo", "reminders", "shell", "system"]
    readonly property string toolsDir: Quickshell.shellPath("../tools")
    // One list for all mascots, in Markdown ("- [ ] item"), kept in the data directory
    readonly property string todoFile: `${bubble.dataDir}/todo.md`
    // Also one for all mascots, "- YYYY-MM-DD HH:MM[:SS] text" lines, see reminders
    readonly property string reminderFile: `${bubble.dataDir}/reminders.md`

    function toolNames(): var {
        return (bubble.event?.tools ?? "").split(",").map(t => t.trim().toLowerCase())
            .filter((t, i, all) => t in bubble.toolFunctions && all.indexOf(t) === i);
    }

    // The environment that gives aichat these tools; local: the local model's
    // Ollama name (e.g. "gemma4-16k") or "", so localTools are among them
    // (tools/mascot-tools also refuses them without it); look_at_image shows
    // the image to that model
    function toolEnvironment(tools: var, local: string): var {
        // No flatMap in Qt's JavaScript engine
        const names = [].concat(...tools.filter(t => local || !bubble.localTools.includes(t)).map(t => bubble.toolFunctions[t]));
        if (!names.length)
            return { AICHAT_FUNCTION_CALLING: "false" };
        return {
            AICHAT_FUNCTIONS_DIR: bubble.toolsDir,
            AICHAT_FUNCTION_CALLING: "true",
            AICHAT_USE_TOOLS: names.join(","),
            MASCOT_TOOLS_LOCAL: local ? "1" : "0",
            MASCOT_VISION_MODEL: local,
            MASCOT_DOTFILES: bubble.event?.dotfiles ?? "",
            MASCOT_TODO_FILE: bubble.todoFile,
            MASCOT_REMINDER_FILE: bubble.reminderFile,
            // CHAT_LANGUAGE: each tool's answer ends with it (gemma4 drifted to Norwegian after one)
            MASCOT_LANGUAGE: bubble.event?.language ?? "",
            // For sleep_mode, which tells the daemon
            MASCOT_CHAT_SOCKET: bubble.chatSocket
        };
    }

    // The daemon's chat socket, for sleep_mode (.quiet), which tells the daemon
    readonly property string chatSocket: Quickshell.env("MASCOT_CHAT_SOCKET")
        || `${Quickshell.env("XDG_RUNTIME_DIR")}/mascotd-chat.sock`

    // Runs one of Mascot's tools itself, not through the model (.todo); its
    // output is written into the conversation
    function runTool(name: string, args: var): void {
        const path = `${bubble.toolsDir}/bin/${name}`.replace(/'/g, "'\\''");
        run([JSON.stringify(args)], false, "system", null, bubble.current, `'${path}'`,
            { MASCOT_TOOLS_LOCAL: "1", MASCOT_TODO_FILE: bubble.todoFile, MASCOT_REMINDER_FILE: bubble.reminderFile,
              MASCOT_CHAT_SOCKET: bubble.chatSocket });
    }

    // Ollama models kept loaded while the bubble is open (OLLAMA_KEEP_ALIVE may
    // unload them after every answer, and loading one takes seconds; it then
    // also reuses the role and tools it read before): name -> true
    property var warmModels: ({})

    function ollama(model: string, keepAlive: var): void {
        const host = Quickshell.env("OLLAMA_HOST") || "127.0.0.1:11434";
        const url = `${host.includes("://") ? host : "http://" + host}`.replace(/\/+$/, "") + "/api/generate";
        // Detached, so the unload still goes out when the bubble quits
        Quickshell.execDetached(["curl", "-s", "-o", "/dev/null", "-m", "30", url,
                                 "-d", JSON.stringify({ model: model, keep_alive: keepAlive })]);
    }

    // Loads the mascot's model if it is a local one, for 10 minutes at most
    // (should the bubble never say it closed), and again with each message
    function warmUp(c: QtObject, command: string): void {
        const probe = (c.model ? ["-m", c.model] : []).concat(roleFlags(), "-s", "mascot-probe");
        lookup(probe, c, command, (info, ok) => {
            const local = ok ? info.match(/^model:?\s+ollama:(\S+)/m) : null;
            if (!local || !bubble.visible)
                return;
            bubble.warmModels[local[1]] = true;
            ollama(local[1], "10m");
        });
    }

    // The bubble closed: unload them again (a running answer finishes first)
    function coolDown(): void {
        for (const model in bubble.warmModels)
            ollama(model, 0);
        bubble.warmModels = {};
    }

    // aichat --info for these args, asked once per bubble: done(info, ok)
    property var lookups: ({})

    function lookup(args: var, c: QtObject, command: string, done: var): void {
        const key = JSON.stringify([command, args]);
        if (key in bubble.lookups) {
            done(bubble.lookups[key], true);
            return;
        }
        run(args.concat("--info"), false, "", (info, ok) => {
            if (ok)
                bubble.lookups[key] = info;
            done(info, ok);
        }, c, command);
    }

    // The role or prompt flags for a message with the tools, and their
    // environment: done(flags, env). aichat gives a role's own use_tools
    // precedence over AICHAT_USE_TOOLS (and --prompt makes a role with none), so
    // with tools the role is sent as --prompt=<its front matter and text> with
    // Mascot's tools as use_tools, and its model as -m (a --prompt keeps none).
    // The file and todo tools (localTools) are offered only when a local model
    // (ollama:…) answers, so what they read stays on this computer, and in a
    // .session (it outlives Mascot) only a private one, which only local models
    // may go on with (see sessionKind()): aichat --info on a fresh session says
    // which model that is, as .model and the role may each choose it
    function withTools(c: QtObject, command: string, done: var): void {
        const tools = toolNames();
        const role = roleFlags();
        if (!tools.length) {
            done(role, toolEnvironment([], ""));
            return;
        }
        const build = (meta, prompt) => {
            const roleModel = (meta.find(l => /^model:/.test(l)) ?? "").replace(/^model:\s*/, "").trim();
            const model = c.model || !roleModel ? [] : ["-m", roleModel];
            const send = local => {
                const env = toolEnvironment(tools, local);
                if (!env.AICHAT_USE_TOOLS) {
                    done(role, env);
                    return;
                }
                const front = meta.filter(l => !/^use_tools:/.test(l)).concat(`use_tools: ${env.AICHAT_USE_TOOLS}`);
                // Otherwise the user has to know what the mascot can do
                const offer = "\n\nWhen one of your tools could help with what the user is doing or asking about, "
                    + "offer it in a few words or just use it - but only the tools you have, and not in every answer.";
                // Models like to say they noted something without doing it
                const todo = env.AICHAT_USE_TOOLS.includes("add_todo") ? "\n\nYou keep the user's todo list with the "
                    + "tools list_todos, add_todo, remove_todo and edit_todo. When the user wants something on it, off it, "
                    + "changed or looked up, call the tool; never say you added, removed or changed something without "
                    + "calling it. To remove several, name them all in one remove_todo call (the numbers change after "
                    + "a removal). The user "
                    + "never sees what a tool returns: when they want to see the list, write it out." : "";
                // Where the user's configs are, so it does not ask for the path
                const dotfiles = (env.MASCOT_DOTFILES ?? "").split(";").map(d => d.trim()).filter(d => d);
                const files = env.AICHAT_USE_TOOLS.includes("read_file") ? "\n\nYou can read the user's files yourself "
                    + "with read_file and list_directory: when they mention one, find it and read it with the tools - do "
                    + "not ask them for the path, and do not say you will look without calling a tool. When you do not "
                    + "know a file's exact name, look it up with list_directory instead of guessing. For a question "
                    + "about part of a file (a setting, a key binding), or a big file, use search_file instead of "
                    + "reading it whole. " + (dotfiles.length
                        ? `Of their hidden files and config directories you may see only these: ${dotfiles.join(", ")}; `
                            + "anything else hidden is off limits, so say so."
                        : "You may not see their hidden files (dotfiles, ~/.config).") : "";
                const remind = env.AICHAT_USE_TOOLS.includes("set_reminder") ? "\n\nWhen the user wants a reminder or "
                    + "a timer, call set_reminder (list_reminders and cancel_reminder for the ones set); the bubble "
                    + "tells them when it is time, so never say you set one without calling it." : "";
                const shell = env.AICHAT_USE_TOOLS.includes("last_commands") ? "\n\nWhen the user asks about a "
                    + "command they ran (the last one, what they just did in the terminal), call last_commands instead "
                    + "of asking them for it, and explain it." : "";
                const sleep = env.AICHAT_USE_TOOLS.includes("sleep_mode") ? "\n\nWhen the user wants quiet or to "
                    + "focus, or asks you to sleep for a while, call sleep_mode; never say you will sleep without "
                    + "calling it." : "";
                // It may only look: the user runs the fix
                const system = env.AICHAT_USE_TOOLS.includes("check_system") ? "\n\nWhen the user asks why something "
                    + "on their computer does not work (the network, a game's LAN, sound, a program that crashes, a "
                    + "service), or how their machine is doing (hot, loud, slow, memory or disks full: area machine), or how the "
                    + "CPU is set to run (its governor, power profile: area power), call "
                    + "check_system for that area first, and read_log to dig further. The machine's readings change all "
                    + "the time: call check_system again for every new question about it, even right after the last. Base your answer "
                    + "only on what they show: say what you found, and when they found nothing that explains it, or "
                    + "could not see something, say so plainly instead of guessing. You cannot change anything: give "
                    + "the exact command that fixes it (with sudo when it needs it), and never say you ran it." : "";
                // A role does not get CHAT_LANGUAGE's note (see roleFlags()), and after
                // the tools' English a model drifts (gemma4: from Danish to Norwegian)
                const language = bubble.event?.language ? `\n\nThe tools answer in English, but you answer in `
                    + `${bubble.event.language} unless the user writes in another language.` : "";
                done(model.concat(`--prompt=---\n${front.join("\n")}\n---\n${prompt}${offer}${files}${todo}${remind}${shell}${sleep}${system}${language}`), env);
            };
            if (!tools.some(t => bubble.localTools.includes(t)) || (c.session && bubble.sessionKinds[c.session] !== "private")) {
                send("");
                return;
            }
            const probe = (c.model ? ["-m", c.model] : []).concat(role, "-s", "mascot-probe");
            lookup(probe, c, command, (info, ok) => {
                const local = ok ? info.match(/^model:?\s+ollama:(\S+)/m) : null;
                send(local ? local[1] : "");
            });
        };
        if (role[0] !== "-r") {
            build([], role[1] ?? ""); // Mascot's prompt, or none
            return;
        }
        // "---\n<front matter>\n---\n\n<prompt>"
        lookup(role, c, command, (info, ok) => {
            if (!ok) {
                done(role, toolEnvironment([], "")); // aichat says why with the message
                return;
            }
            const parts = info.match(/^---\n([\s\S]*?)\n---\n\n?([\s\S]*)$/);
            build(parts ? parts[1].split("\n") : [], (parts ? parts[2] : info).trim());
        });
    }

    // Sends a message to the current mascot; kind of the answer's entry:
    // "reply" or "remark". It goes into the mascot's own memory unless .session
    // chose a session. A session keeps the role or prompt (and the tools) its
    // first message had and ignores later ones (and aichat skips cmd_prelude
    // with -s), so a new role, mascot name or set of tools starts the memory
    // over - also when a model that is not local takes over, so what the file
    // and todo tools read never goes to it
    function ask(text: string, kind: string): void {
        const c = bubble.current;
        c.readFrom = -1;
        const command = bubble.event?.command || "aichat";
        if (c.session) {
            sessionKind(c, command, ok => ok && askWithTools(text, kind, c, command));
            return;
        }
        askWithTools(text, kind, c, command);
    }

    // A .session is "private" when its first message went to a local model:
    // it gets the file, todo and other local tools, and so holds what they
    // read, which must stay on this computer - only a local model may go on
    // with it. Any other is "open": no local tools, any model. One Mascot
    // did not start (made in a terminal, or before this) counts as open.
    // Kept in the data directory, as sessions outlive Mascot
    property var sessionKinds: ({})

    FileView {
        id: sessionKindsView

        path: `${bubble.dataDir}/sessions`
        printErrors: false
        onLoaded: {
            try {
                bubble.sessionKinds = JSON.parse(this.text()) ?? {};
            } catch (e) {}
        }
    }

    // A private session goes on only with a local model: when it is chosen
    // with another one, the default model if that is local, else the local
    // model used last, else aichat's first
    function localForPrivate(c: QtObject): void {
        const command = bubble.event?.command || "aichat";
        const isLocal = (model, done) => lookup((model ? ["-m", model] : []).concat(roleFlags(), "-s", "mascot-probe"), c, command,
                                                (info, ok) => done(ok && /^model:?\s+ollama:/m.test(info)));
        const use = model => {
            c.model = model;
            c.entries.append({ kind: "system", body: `model: ${model || defaultName("model")} - ${c.session} is a private `
                + "session, so it goes on with a local model" });
        };
        isLocal(c.model, local => {
            if (local)
                return;
            isLocal("", defaultLocal => {
                if (defaultLocal) {
                    use("");
                    return;
                }
                const used = bubble.usedModels.find(m => m.startsWith("ollama:"));
                if (used) {
                    use(used);
                    return;
                }
                run(["--list-models"], false, "", (list, ok) => {
                    const first = ok ? list.split("\n").map(l => l.trim()).find(m => m.startsWith("ollama:")) : null;
                    if (first)
                        use(first);
                    else
                        c.entries.append({ kind: "system", body: `${c.session} is a private session, but aichat has no `
                            + "local (ollama:) model to go on with it" });
                }, c, command);
            });
        });
    }

    // .delete session <name>: deletes one of aichat's sessions (it has no
    // command for it): its file in aichat's sessions_dir, after the menu's
    // "Delete session ›" typed it for Enter to confirm
    function deleteSession(name: string): void {
        const c = bubble.current;
        const command = bubble.event?.command || "aichat";
        const say = text => c.entries.append({ kind: "system", body: text });
        if (!name || name.includes("/") || name.startsWith(".")) {
            say(`no session called ${name}`);
            return;
        }
        // Not the bubble's memory dir (see run()), aichat's own
        run(["--info"], false, "", (info, ok) => {
            const dir = ok ? (info.match(/^sessions_dir:?\s+(\S.*)$/m) ?? [])[1] : null;
            if (!dir) {
                say("cannot tell where aichat keeps its sessions");
                return;
            }
            run(["--", `${dir.trim()}/${name}.yaml`], false, "", (out, removed) => {
                if (!removed) {
                    say(`no session called ${name}`);
                    return;
                }
                const kinds = Object.assign({}, bubble.sessionKinds);
                delete kinds[name];
                bubble.sessionKinds = kinds;
                sessionKindsView.setText(JSON.stringify(kinds, null, 1) + "\n");
                for (const id in bubble.conversations)
                    if (bubble.conversations[id].session === name)
                        bubble.conversations[id].session = "";
                say(`deleted session ${name}`);
            }, c, "rm");
        }, c, command, { AICHAT_SESSIONS_DIR: null });
    }

    // For .tools: whether the local tools are there in this .session
    function sessionNote(): string {
        const session = chosen().session;
        if (!session)
            return "";
        const kind = bubble.sessionKinds[session];
        return kind === "private" ? `; ${session} is a private session, so only local models go on with it`
            : kind === "open" ? `; not in ${session}, which a model online may see`
            : `; in ${session} only if its first message goes to a local model (a private session)`;
    }

    // done(ok): ok when the message may go to c.session with this model
    function sessionKind(c: QtObject, command: string, done: var): void {
        const probe = (c.model ? ["-m", c.model] : []).concat(roleFlags(), "-s", "mascot-probe");
        lookup(probe, c, command, (info, ok) => {
            const local = ok && /^model:?\s+ollama:/m.test(info);
            const kind = bubble.sessionKinds[c.session];
            if (kind === "private" && !local) {
                c.entries.append({ kind: "system", body: `${c.session} is a private session: it holds what your `
                    + "files, todo list and history said, so only a local (ollama:) model may go on with it - pick one "
                    + "under Settings › Model, or .exit session" });
                done(false);
                return;
            }
            if (kind) {
                done(true);
                return;
            }
            // New: it takes after the model of its first message; one aichat
            // has already is open
            run(["--list-sessions"], false, "", (list, listed) => {
                const known = listed && list.split("\n").map(l => l.trim()).includes(c.session);
                // A new object, so the menu's binding sees it
                bubble.sessionKinds = Object.assign({}, bubble.sessionKinds, { [c.session]: !known && local ? "private" : "open" });
                sessionKindsView.setText(JSON.stringify(bubble.sessionKinds, null, 1) + "\n");
                done(true);
            }, c, command);
        });
    }

    function askWithTools(text: string, kind: string, c: QtObject, command: string): void {
        warmUp(c, command);
        withTools(c, command, (persona, env) => {
            // The model always knows the time, without a tool call, which not
            // every model makes; not shown, but kept in the memory
            if (toolNames().includes("time"))
                text = `(Now: ${Qt.formatDateTime(new Date(), "dddd yyyy-MM-dd HH:mm")})\n\n${text}`;
            const base = (c.model ? ["-m", c.model] : []).concat(persona);
            if (c.session) {
                // "--": a message may start with '-'
                run(base.concat("-s", c.session, "--save-session", "--", text), true, kind, null, c, command, env);
                return;
            }
            const key = JSON.stringify(persona);
            if (c.memory && c.persona !== key) {
                const local = /read_file|list_todos|list_reminders|last_commands/;
                c.entries.append({ kind: "system", body: local.test(c.persona) && !local.test(key)
                    ? "not a local model - no files, todo list, reminders or shell history, and the memory starts over, so what the mascot read stays here"
                    : "new role or tools - the memory starts over" });
                c.memory = "";
            }
            if (!c.memory) {
                c.memory = `chat-${++bubble.memoryCount}`;
                c.persona = key;
                c.memoryChars = 0;
            }
            remember(text, kind, c, command, base, env);
        });
    }

    // The rest of ask(): sends text into the memory with these tools (env), and
    // sums the memory up first if it has grown past memoryFor()
    function remember(text: string, kind: string, c: QtObject, command: string, base: var, env: var): void {
        memoryFor(c, command, limit => rememberWithin(limit, text, kind, c, command, base, env));
    }

    function rememberWithin(limit: int, text: string, kind: string, c: QtObject, command: string, base: var, env: var): void {
        const post = message => {
            c.memoryChars += message.length;
            run(base.concat("-s", c.memory, "--save-session", "--", message), true, kind, null, c, command, env);
        };
        if (!limit || c.memoryChars <= limit) {
            post(text);
            return;
        }
        say("summing up the memory…");
        run(base.concat("-s", c.memory, "--", "(Not from the user: sum up our conversation so far in a few short "
            + "sentences, for your own memory - names, facts, what we talked about and how. Write only the "
            + "summary, in the language of the conversation.)"), false, "", (summary, ok) => {
            // Without the model's reasoning: in a user message it is not hidden,
            // and gemma4 then answers with its raw template tokens
            summary = answerOf(summary);
            // Failed: carry on in the long memory rather than lose it
            if (ok && summary) {
                c.memory = `chat-${++bubble.memoryCount}`;
                c.memoryChars = 0;
                text = `(What we talked about before, summed up: ${summary})\n\n${text}`;
            }
            post(text);
        }, c, command, toolEnvironment([], ""));
    }

    // Runs CHAT_COMMAND with args appended; they are passed as "$@", never
    // parsed by the shell. kind of the entry it writes into: "reply" for a
    // message (or "remark"), "system" for a dot command, "" for none: the
    // output is then collected and handed to done(output, ok) instead; env:
    // more environment for it, e.g. toolEnvironment()
    function run(args: var, reply = false, kind = reply ? "reply" : "system", done = null,
                 c = bubble.current, command = bubble.event?.command || "aichat", env = ({})): void {
        if (kind) {
            c.entries.append({ kind: kind, body: "" });
            c.streaming = c.entries.count - 1;
        } else {
            c.streaming = -1;
        }
        c.replying = reply;
        c.doing = "";
        c.doingIcon = "";
        c.toolKind = "";
        c.unsure = false;
        c.found = false;
        c.ticked = false;
        c.fullPower = false;
        c.job = jobComponent.createObject(bubble, {
            conv: c,
            done: done,
            // Only the mascot's memory uses the bubble's memory dir: .sessions
            // and named sessions stay in aichat's own
            environment: Object.assign((reply || !kind) && !c.session ? { AICHAT_SESSIONS_DIR: bubble.memoryDir } : {}, env),
            // stdin must be closed: aichat reads a non-tty stdin as extra input
            // and waits forever on the open pipe Process gives it
            command: ["sh", "-c", command + ' "$@" </dev/null', "mascot-bubble"].concat(args)
        });
        c.job.running = true;
    }

    function scrollBy(dy: real): void {
        scroller.contentY = Math.max(0, Math.min(scroller.contentY + dy, scroller.contentHeight - scroller.height));
    }

    // A Nerd Font for the icons, if one is installed (they take the text's
    // pywal colour); without one, emoji
    readonly property string nerdFont: Qt.fontFamilies().find(f => /^Symbols Nerd Font$/.test(f))
        ?? Qt.fontFamilies().find(f => /Nerd Font$/.test(f)) ?? ""

    // An icon by name: a Nerd Font (Font Awesome) glyph, else an emoji
    function icon(name: string): string {
        const icons = {
            weather: ["\uf0c2", "☁"], folder: ["\uf07c", "📁"], file: ["\uf15c", "📄"], search: ["\uf002", "🔍"],
            image: ["\uf03e", "🖼"], todo: ["\uf0ae", "📝"], reminder: ["\uf017", "⏰"], shell: ["\uf120", "⌨"],
            sleep: ["\uf186", "💤"], system: ["\uf2db", "🔧"], machine: ["\uf080", "📊"], power: ["\uf0e7", "⚡"], check: ["\uf00c", "✓"]
        };
        return (icons[name] ?? ["", ""])[bubble.nerdFont ? 0 : 1];
    }

    // What a tool is doing, from its "mascot-doing: {tool, args}" on stderr,
    // shown by the thinking dots until the answer starts: [icon, text]
    function doingOf(json: string): var {
        let d;
        try {
            d = JSON.parse(json);
        } catch (e) {
            return ["", ""];
        }
        const a = d.args ?? {};
        const file = p => String(p ?? "").replace(/\/+$/, "").split("/").pop() || "your files";
        switch (d.tool) {
        case "get_current_weather":
            return ["weather", a.location ? `checking the weather in ${a.location}…` : "checking the weather…"];
        case "list_directory":
            return ["folder", `looking in ${file(a.path)}…`];
        case "read_file":
            return ["file", `reading ${file(a.path)}…`];
        case "search_file":
            return ["search", `searching ${file(a.path)}…`];
        case "look_at_image":
            return ["image", `looking at ${file(a.path)}…`];
        case "list_todos":
            return ["todo", "checking the todo list…"];
        case "add_todo":
        case "remove_todo":
        case "edit_todo":
            return ["todo", "updating the todo list…"];
        case "set_reminder":
            return ["reminder", "setting a reminder…"];
        case "list_reminders":
        case "cancel_reminder":
            return ["reminder", "checking the reminders…"];
        case "last_commands":
            return ["shell", "looking at your last commands…"];
        case "sleep_mode":
            return ["sleep", "getting sleepy…"];
        case "check_system":
            if (a.area === "machine")
                return ["machine", "checking the machine…"];
            if (a.area === "power")
                return ["power", "checking how the CPU runs…"];
            return ["system", { network: "checking the network…", sound: "checking the sound…",
                crashes: "looking for crashes…", services: "checking the services…" }[a.area] ?? "checking the system…"];
        case "read_log":
            return ["system", a.search ? `searching the log for ${a.search}…` : "reading the system's log…"];
        }
        return ["", ""];
    }

    // The answer without a reasoning model's <think>…</think>
    function answerOf(body: string): string {
        return body.replace(/<(think|thinking)>[\s\S]*?(<\/\1>|$)/g, "").trim();
    }

    // The entry with text selected by the mouse, for Ctrl+C in the input
    property Item selected: null

    function copySelection(): bool {
        const text = bubble.selected?.selectedText ?? "";
        if (!text)
            return false;
        Quickshell.clipboardText = text;
        return true;
    }

    function say(text: string): void {
        bubble.entries.append({ kind: "system", body: text });
    }

    function defaultName(key: string): string {
        if (key !== "role")
            return "default";
        if (bubble.event.role && !chosen().noRole)
            return `${bubble.event.role} (default)`;
        return bubble.event?.prompt ? "none (the mascot's own prompt)"
            : bubble.prompt ? "none (Mascot's prompt)" : "none (aichat's default)";
    }

    function dotCommand(text: string): void {
        bubble.current.readFrom = bubble.entries.count - 1;
        const [name, ...rest] = text.split(/\s+/);
        const arg = rest.join(" ");
        switch (name) {
        case ".help":
            say(arg === "all" ? helpText : helpShort);
            return;
        case ".info":
            {
                // And how much the mascot remembers before it sums up (memoryFor());
                // in a .session aichat sums up itself, past its compress_threshold
                const c = bubble.current;
                const command = bubble.event?.command || "aichat";
                // The running mascotd's: an older one wants a restart after an update
                c.entries.append({ kind: "system", body: `Mascot ${bubble.event?.version || "(restart Mascot to see its version)"}` });
                if (c.session) {
                    lookup([], c, command, (info, ok) => {
                        const threshold = ok ? (info.match(/^compress_threshold:?\s+(\d+)/m) ?? [])[1] : null;
                        run(flags().concat("--info"), false, "system", null, c, command);
                        c.entries.append({ kind: "system", body: threshold && threshold !== "0"
                            ? `memory: aichat's session ${c.session}, summed up by aichat past ${threshold} tokens (compress_threshold)`
                            : `memory: aichat's session ${c.session}, never summed up (compress_threshold)` });
                        if (bubble.sessionKinds[c.session] === "private")
                            c.entries.append({ kind: "system", body: `${c.session} is a private session: `
                                + "it has the local tools, and only local models may go on with it" });
                    });
                    return;
                }
                memoryFor(c, command, (limit, why) => {
                    run(flags().concat("--info"), false, "system", null, c, command);
                    c.entries.append({ kind: "system", body: limit
                        ? `memory: about ${Math.round(limit / 3)} tokens before it is summed up (${why})`
                        : `memory: never summed up (${why})` });
                });
                return;
            }
        case ".models":
            if (arg)
                searchOpenRouter(arg);
            else
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
                const c = chosen();
                if (arg) {
                    c[key] = arg;
                    if (key === "role")
                        c.noRole = false;
                }
                say(`${key}: ${c[key] || defaultName(key)}`);
                if (key === "session" && arg && bubble.sessionKinds[arg] === "private")
                    localForPrivate(c);
                return;
            }
        case ".delete":
            if (rest[0] !== "session" || rest.length < 2)
                say("use .delete session <name>");
            else
                deleteSession(rest.slice(1).join(" "));
            return;
        case ".exit":
            if (!["model", "role", "session"].includes(arg)) {
                say("use .exit model, .exit role or .exit session");
                return;
            }
            chosen()[arg] = "";
            if (arg === "role")
                chosen().noRole = true;
            say(`${arg}: ${defaultName(arg)}`);
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
        case ".tools":
            {
                const tools = toolNames();
                if (!tools.length) {
                    say("tools: none (set CHAT_TOOLS to time, weather, files, todo, reminders, shell and/or sleep)");
                    return;
                }
                const notes = {
                    time: "time - the date and time, sent with every message",
                    weather: "weather - from wttr.in (only the place name is sent)",
                    files: "files - lists and reads files and looks at images in your home directory, "
                        + "dotfiles only those in CHAT_DOTFILES, never where keys, logins or history are kept, "
                        + "and only with a local (ollama:) model" + bubble.sessionNote(),
                    todo: "todo - shows, adds to, changes and removes from your todo list (also .todo), "
                        + "only with a local (ollama:) model" + bubble.sessionNote(),
                    reminders: "reminders - sets, lists and cancels reminders and timers (also .remind), "
                        + "only with a local (ollama:) model" + bubble.sessionNote(),
                    shell: "shell - the last commands you ran (zsh, bash or fish history), hiding those that may "
                        + "hold a password or key, only with a local (ollama:) model"
                        + bubble.sessionNote(),
                    sleep: "sleep - the mascots sleep for a while when you ask (do not disturb: no remarks, "
                        + "reminders wait), also mascot sleep --minutes"
                };
                say(tools.map(t => notes[t]).join("\n"));
                return;
            }
        case ".todo":
            {
                const [sub, ...words] = rest;
                const item = words.join(" ");
                // .todo edit <number> <new text>: by number, as the text may be anything
                if (sub === "edit") {
                    if (/^\d+$/.test(words[0] ?? "") && words.length > 1)
                        runTool("edit_todo", { item: words[0], text: words.slice(1).join(" ") });
                    else
                        say("use .todo edit <number> <new text>");
                    return;
                }
                const tool = !sub ? "list_todos" : sub === "add" ? "add_todo"
                    : ["done", "remove", "rm"].includes(sub) ? "remove_todo" : "";
                if (!tool || (sub && !item))
                    say("use .todo, .todo add <item>, .todo done <number or text> or .todo edit <number> <new text>");
                else
                    runTool(tool, sub ? { item: item } : {});
                return;
            }
        case ".remind":
        case ".reminders":
            {
                const cancel = ["cancel", "rm", "remove"].includes(rest[0]);
                if (name === ".reminders" || (!arg && name === ".remind"))
                    runTool("list_reminders", {});
                else if (cancel && rest.length > 1)
                    runTool("cancel_reminder", { item: rest.slice(1).join(" ") });
                else if (cancel)
                    say("use .remind cancel <number or text>");
                else
                    runTool("set_reminder", { text: arg }); // it finds the time at the start
                return;
            }
        case ".quiet":
            if (!arg)
                say("use .quiet <when>, e.g. .quiet 10m, .quiet 2h or .quiet 19:30 (.quiet now wakes them)");
            else
                runTool("sleep_mode", { wake_up: arg });
            return;
        case ".copy":
            for (let i = bubble.entries.count - 1; i >= 0; i--) {
                const e = bubble.entries.get(i);
                if ((e.kind === "reply" || e.kind === "remark") && answerOf(e.body)) {
                    Quickshell.clipboardText = answerOf(e.body);
                    say("copied the last answer");
                    return;
                }
            }
            say("no answer to copy yet");
            return;
        case ".clear":
            stop(bubble.current);
            bubble.entries.clear();
            bubble.current.memory = "";
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

        bubble.current.error = "";
        bubble.entries.append({ kind: "you", body: text });
        input.text = "";
        if (text.startsWith("."))
            dotCommand(text);
        else
            ask(text, "reply");
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
    // OnDemand alone only focuses on click, so open as Exclusive to type straight
    // away, then drop to OnDemand (see grabKeyboard())
    WlrLayershell.keyboardFocus: bubble.grabbing || bubble.keepKeyboard ? WlrKeyboardFocus.Exclusive
        : bubble.remarking ? WlrKeyboardFocus.None : WlrKeyboardFocus.OnDemand

    // For the right-click menu (Menu.qml)
    readonly property QtObject colors: theme

    // Colours from pywal (read only), with fallbacks if the cache is missing
    QtObject {
        id: theme

        property color background: "#1e1e2e"
        property color foreground: "#cdd6f4"
        property color accent: "#89b4fa"
        property color muted: "#a6adc8"
        property color remark: "#cba6f7" // what a mascot said on its own

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
            theme.remark = data.colors?.color5 ?? theme.remark;
        }
    }

    // The system prompt, used unless a role is chosen (.role, CHAT_ROLES,
    // CHAT_ROLE); {name} is the mascot's name. A mascot's own prompt.md (the
    // daemon sends it with the tap, e.g. Robo's) comes first; else a prompt.md in
    // the data directory replaces Mascot's bundled one (an empty one turns the
    // prompt off). Read when the bubble starts
    readonly property string dataDir: Quickshell.env("MASCOT_DATA_DIR")
        || `${Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share"}/mascot`
    property var userPrompt: null // null: no prompt.md in dataDir
    property string bundledPrompt: ""
    readonly property string prompt: (bubble.event?.prompt || (userPrompt ?? bundledPrompt)).trim()

    FileView {
        path: `${bubble.dataDir}/prompt.md`
        printErrors: false
        onLoaded: bubble.userPrompt = this.text()
    }

    // The models (.model) that have answered, newest first, for the menu: a
    // model aichat does not list (its list of OpenRouter's is old) is there
    // the next time. One per line in the data directory
    property var usedModels: []

    function rememberModel(model: string): void {
        if (bubble.usedModels[0] === model)
            return;
        bubble.usedModels = [model].concat(bubble.usedModels.filter(m => m !== model)).slice(0, 10);
        usedModelsView.setText(bubble.usedModels.join("\n") + "\n");
    }

    FileView {
        id: usedModelsView

        path: `${bubble.dataDir}/models`
        printErrors: false
        onLoaded: bubble.usedModels = this.text().split("\n").map(l => l.trim()).filter(l => l)
    }

    // The models OpenRouter has now (its public list, no key needed), asked for
    // once: openRouterList has them newest first, openRouterModels by id for
    // the menu, which leaves out the ones that are gone. null: not known (yet,
    // or no network)
    property var openRouterList: null
    property var openRouterModels: null
    property var openRouterWaiting: [] // done(ok) for each, while asking
    property bool askingOpenRouter: false

    function askOpenRouter(done: var): void {
        if (bubble.openRouterList) {
            if (done)
                done(true);
            return;
        }
        if (done)
            bubble.openRouterWaiting.push(done);
        if (bubble.askingOpenRouter)
            return;
        bubble.askingOpenRouter = true;
        const request = new XMLHttpRequest();
        request.onreadystatechange = () => {
            if (request.readyState !== XMLHttpRequest.DONE)
                return;
            bubble.askingOpenRouter = false;
            try {
                if (request.status === 200) {
                    const list = JSON.parse(request.responseText).data;
                    list.sort((a, b) => (b.created ?? 0) - (a.created ?? 0));
                    const ids = {};
                    for (const model of list)
                        ids[model.id] = true;
                    bubble.openRouterList = list;
                    bubble.openRouterModels = ids;
                }
            } catch (e) {}
            const waiting = bubble.openRouterWaiting;
            bubble.openRouterWaiting = [];
            for (const each of waiting)
                each(!!bubble.openRouterList);
        };
        request.open("GET", "https://openrouter.ai/api/v1/models");
        request.send();
    }

    // .models <search>: OpenRouter's models whose id or name has every word,
    // newest first, with the price of a million tokens in, the context and
    // whether it can use Mascot's tools; not the :batch ones, which are not
    // for chatting
    function searchOpenRouter(search: string): void {
        const c = bubble.current;
        const words = search.toLowerCase().split(/\s+/);
        bubble.askOpenRouter(ok => {
            const say = text => c.entries.append({ kind: "system", body: text });
            if (!ok) {
                say("cannot reach OpenRouter (openrouter.ai/models lists them too)");
                return;
            }
            const found = bubble.openRouterList.filter(m => !m.id.endsWith(":batch")
                && words.every(w => `${m.id} ${m.name ?? ""}`.toLowerCase().includes(w)));
            if (!found.length) {
                say(`OpenRouter has no model with "${search}"`);
                return;
            }
            const size = n => !n ? "?" : n >= 1e6 ? `${Math.round(n / 1e5) / 10}M` : `${Math.round(n / 1000)}k`;
            const price = m => {
                const p = parseFloat(m.pricing?.prompt ?? "");
                return isNaN(p) ? "?" : p === 0 ? "free" : `$${(p * 1e6).toFixed(2)}`;
            };
            const shown = found.slice(0, 15);
            // The id on a line of its own, as the bubble is narrow
            const lines = shown.map(m => `${m.id}\n   ${price(m)}/M in · ${size(m.context_length)} context`
                + ((m.supported_parameters ?? []).includes("tools") ? " · tools" : ""));
            c.entries.append({ kind: "listing", body: lines.join("\n") });
            say((found.length > shown.length ? `the newest ${shown.length} of ${found.length}; ` : "")
                + "use one with .model openrouter:<model> (with tools it can tell the time and weather)");
        });
    }

    // aichat's error, with what to do about the ones that need it
    // What went wrong, said so that someone new to aichat knows what to do (the
    // error itself follows)
    // aichat's "Error: what\n\nCaused by:\n    why" on one line ("what: why"), so it fits the bubble
    function compact(error: string): string {
        return error.split("\n").map(l => l.trim()).filter(l => l && l !== "Caused by:")
            .map(l => l.replace(/^Error:\s*/, "").replace(/^\d+:\s*/, "")).join(": ");
    }

    function explained(error: string): string {
        error = bubble.compact(error);
        const gone = error.match(/No endpoints found for ([^".]+)/);
        if (gone)
            return `OpenRouter has no model ${gone[1]} (any more) - pick another under Settings › Model, or find one `
                + `on openrouter.ai/models and use .model openrouter:<name>\n${error}`;
        if (/Failed to load config/.test(error))
            return "aichat is not set up yet, so there is no model to answer with. See \"Getting started\" in "
                + `Mascot's README: a free local model with Ollama, or a hosted one with OpenRouter.\n${error}`;
        if (/aichat: (command )?not found/.test(error))
            return `aichat is not installed: install it (on Arch: pacman -S aichat), then set it up as `
                + `"Getting started" in Mascot's README says.\n${error}`;
        const missing = error.match(/model '([^']+)' not found/);
        if (missing)
            return `The model ${missing[1]} is not there - if it is a local one, download it with: ollama pull `
                + `${missing[1].replace(/^ollama:/, "")}\n${error}`;
        const unreachable = error.match(/error sending request for url \((https?:\/\/[^/)]+)/);
        if (unreachable)
            return (/:11434$/.test(unreachable[1])
                ? "Ollama does not answer - is it running? Start it with: systemctl start ollama"
                : `Nothing answers at ${unreachable[1]} - check your network, or the address in aichat's config`)
                + `\n${error}`;
        return error;
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

    // One per command run, writing into its own conversation, see run()
    Component {
        id: jobComponent

        Process {
            id: job

            property QtObject conv
            property var done: null // see run()
            property string output: ""

            stdout: SplitParser {
                splitMarker: "" // stream: append chunks as they arrive
                onRead: data => {
                    const c = job.conv;
                    if (c?.job !== job)
                        return;
                    if (c.streaming < 0)
                        job.output += data;
                    else if (c.streaming < c.entries.count)
                        c.entries.setProperty(c.streaming, "body", c.entries.get(c.streaming).body + data);
                    if (c.toolKind && c.streaming >= 0 && c.streaming < c.entries.count
                            && bubble.answerOf(c.entries.get(c.streaming).body))
                        c.toolKind = c.unsure && !c.found ? "unsure" : c.ticked ? "done" : c.fullPower ? "fullpower" : "";
                }
            }
            // Line by line, so what a tool starts doing shows while it runs
            property string errors: ""
            stderr: SplitParser {
                onRead: line => {
                    job.errors += line + "\n";
                    const c = job.conv;
                    if (c?.job === job && line.startsWith("mascot-doing: ")) {
                        [c.doingIcon, c.doing] = bubble.doingOf(line.slice(14));
                        c.toolKind = c.doingIcon;
                    } else if (c?.job === job && line === "mascot-unsure") {
                        c.unsure = true;
                    } else if (c?.job === job && line === "mascot-found") {
                        c.found = true;
                    } else if (c?.job === job && line === "mascot-done") {
                        c.ticked = true;
                    } else if (c?.job === job && line === "mascot-full-power") {
                        c.fullPower = true;
                    }
                }
            }

            onExited: (exitCode, exitStatus) => {
                const c = job.conv;
                if (c?.job === job) { // not stopped
                    if (exitCode !== 0 && !job.done)
                        c.error = bubble.explained(job.errors.trim()) || `The command failed (exit ${exitCode})`;
                    if (exitCode === 0 && c.replying && c.model)
                        bubble.rememberModel(c.model);
                    // Without the reasoning: aichat keeps it in the session file,
                    // but never sends it to the model again
                    if (c.replying && c.streaming >= 0 && c.streaming < c.entries.count)
                        c.memoryChars += bubble.answerOf(c.entries.get(c.streaming).body).length;
                    if (c.replying)
                        bubble.answered(c);
                    // .todo done (no answer to start): glad for a few seconds all the same
                    else if (c.ticked && bubble.visible && bubble.event && c === bubble.current)
                        bubble.linger("done");
                    // What Mascot's tools really changed (they say so on stderr),
                    // whatever the reply claims
                    if (c.replying) {
                        let todos = null, changes = false;
                        const shows = [];
                        for (const line of job.errors.split("\n")) {
                            if (line.startsWith("mascot-tools: ")) {
                                c.entries.append({ kind: "system", body: "✓ " + line.slice(14) });
                                changes = true;
                            } else if (line.startsWith("mascot-todos: ")) {
                                todos = line.slice(14);
                            } else if (line.startsWith("mascot-show: ")) {
                                shows.push(line.slice(13));
                            } else if (line.startsWith("mascot-size: ")) {
                                c.memoryChars += parseInt(line.slice(13)) || 0; // what a tool put in the memory
                            }
                        }
                        const reply = c.streaming >= 0 && c.streaming < c.entries.count
                            ? c.entries.get(c.streaming).body.toLowerCase() : "";
                        // What a tool drew for the user (a tree), unless the reply has it
                        for (const show of shows) {
                            try {
                                const s = JSON.parse(show);
                                if (!s.names.every(n => reply.includes(n.toLowerCase().replace(/\/$/, ""))))
                                    c.entries.append({ kind: "listing", body: s.text });
                            } catch (e) {}
                        }
                        // The todo list the model looked up, unless its reply has it,
                        // or it was only looked up to change it (the ✓ says what changed)
                        if (todos !== null && !changes) {
                            try {
                                const items = JSON.parse(todos);
                                if (!items.every(t => reply.includes(t.toLowerCase())))
                                    c.entries.append({ kind: "system", body: items.map((t, i) => `${i + 1}. ${t}`).join("\n") });
                            } catch (e) {}
                        }
                    }
                    reminderView.reload();
                    // The job first, so the "?" or the joy of a todo done ends with
                    // the answer and lingers (see onToolPoseChanged)
                    c.job = null;
                    c.toolKind = "";
                    // The answer failed (no Ollama, no model...): the mascot is sad for a few seconds
                    if (exitCode !== 0 && !job.done && c.replying && bubble.visible && bubble.event && c === bubble.current)
                        bubble.linger("failed");
                    if (job.done)
                        job.done(job.output, exitCode === 0);
                }
                job.destroy();
            }
        }
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        visible: !bubble.hiddenForDrag

        HoverHandler {
            id: remarkHover
        }

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

        visible: !bubble.hiddenForDrag
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
            // Gives way to an error, so it and the input stay inside the bubble
            height: Math.max(0, Math.min(log.implicitHeight, 220, bubble.maxBodyHeight - 2 * bubble.padding
                - title.implicitHeight - inputBox.height - content.spacing * (errorText.visible ? 3 : 2)
                - (errorText.visible ? errorText.height : 0)))
            visible: (bubble.entries?.count ?? 0) > 0
            contentHeight: log.implicitHeight
            clip: true
            // A drag selects text instead of scrolling; the wheel still scrolls
            interactive: false

            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: event => bubble.scrollBy(event.pixelDelta.y ? -event.pixelDelta.y : -event.angleDelta.y / 3)
            }

            Column {
                id: log

                width: scroller.width
                spacing: 8

                // Follow the streamed answer; a dot command's output (.info, .help all …)
                // is read from the top, so never past its line
                onImplicitHeightChanged: {
                    const from = entryItems.itemAt(bubble.current?.readFrom ?? -1);
                    scroller.contentY = Math.max(0, Math.min(implicitHeight - scroller.height, from ? from.y : Infinity));
                }

                Repeater {
                    id: entryItems

                    model: bubble.entries

                    TextEdit {
                        id: entry

                        required property string kind
                        required property string body
                        required property int index

                        // Reasoning models write <think>…</think> before the answer: hide it,
                        // and pulse three dots until the answer starts (also while the
                        // model loads and reads the prompt, before it writes anything)
                        readonly property bool answering: kind === "reply" || kind === "remark"
                        readonly property string answer: answering ? bubble.answerOf(body) : body.trim()
                        readonly property bool thinking: answering && answer === ""
                            && bubble.current.streaming === index && !!bubble.current.job

                        width: log.width
                        visible: text !== "" || thinking // a command that has printed nothing yet
                        text: (kind === "you" ? "› " : "") + answer
                        textFormat: TextEdit.PlainText // model output is never markup
                        wrapMode: TextEdit.Wrap
                        // Selectable for copying; the input keeps the keyboard
                        readOnly: true
                        selectByMouse: true
                        activeFocusOnPress: false
                        persistentSelection: true
                        selectionColor: Qt.alpha(theme.accent, 0.4)
                        selectedTextColor: color
                        onSelectedTextChanged: if (selectedText && bubble.selected !== entry) {
                            bubble.selected?.deselect();
                            bubble.selected = entry;
                        }
                        Component.onDestruction: if (bubble.selected === entry)
                            bubble.selected = null
                        color: kind === "you" ? theme.accent : kind === "reply" ? theme.foreground
                            : kind === "remark" || kind === "reminder" ? theme.remark : theme.muted
                        font.pixelSize: 13
                        font.family: kind === "listing" ? "monospace" : Qt.application.font.family

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: entry.thinking
                            spacing: 5

                            Repeater {
                                model: 3

                                Rectangle {
                                    required property int index

                                    width: 6
                                    height: 6
                                    radius: 3
                                    color: entry.kind === "remark" ? theme.remark : theme.accent
                                    opacity: 0.25

                                    // One after the other, like a wave
                                    SequentialAnimation on opacity {
                                        running: entry.thinking
                                        loops: Animation.Infinite
                                        PauseAnimation { duration: index * 160 }
                                        NumberAnimation { to: 1; duration: 320; easing.type: Easing.OutQuad }
                                        NumberAnimation { to: 0.25; duration: 320; easing.type: Easing.InQuad }
                                        PauseAnimation { duration: (2 - index) * 160 }
                                    }
                                }
                            }

                            // What a tool is doing meanwhile (the weather, a file...)
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                leftPadding: 4
                                visible: text !== ""
                                text: bubble.icon(bubble.current?.doingIcon ?? "")
                                color: theme.muted
                                font.pixelSize: 12
                                font.family: bubble.nerdFont || Qt.application.font.family
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: text !== ""
                                text: bubble.current?.doing ?? ""
                                color: theme.muted
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                width: Math.min(implicitWidth, log.width - 40)
                            }
                        }
                    }
                }
            }
        }

        Text {
            id: errorText

            width: parent.width
            visible: !!bubble.current?.error
            text: bubble.current?.error ?? ""
            wrapMode: Text.Wrap
            maximumLineCount: 6
            elide: Text.ElideRight
            color: "#f38ba8"
            font.pixelSize: 12
        }

        Rectangle {
            id: inputBox

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

                onActiveFocusChanged: if (activeFocus)
                    bubble.remarking = false
                Keys.onReturnPressed: bubble.send()
                Keys.onEnterPressed: bubble.send()
                Keys.onEscapePressed: bubble.close()
                // Scroll the conversation: the arrows (a one-line input has no use
                // for them), Ctrl+J/K and PageUp/PageDown; j and k still type
                Keys.onUpPressed: bubble.scrollBy(-40)
                Keys.onDownPressed: bubble.scrollBy(40)
                Keys.onPressed: event => {
                    const ctrl = event.modifiers & Qt.ControlModifier;
                    const step = ctrl && event.key === Qt.Key_K ? -40 : ctrl && event.key === Qt.Key_J ? 40
                        : event.key === Qt.Key_PageUp ? -scroller.height : event.key === Qt.Key_PageDown ? scroller.height : 0;
                    if (step) {
                        bubble.scrollBy(step);
                        event.accepted = true;
                    } else if (ctrl && event.key === Qt.Key_C && !input.selectedText && bubble.copySelection()) {
                        event.accepted = true; // copy what is selected in the conversation
                        copied.restart();
                    } else if (ctrl && event.key === Qt.Key_C && input.selectedText) {
                        copied.restart(); // the input copies its own selection
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: !input.text
                    text: bubble.busy ? "…" : `Message ${bubble.event?.prototype ?? "the mascot"}…  (.help)`
                    color: theme.muted
                    font: input.font
                }
            }

            // Ctrl+C copied something: says so for a moment, then fades
            Text {
                id: copiedLabel

                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: `<font face="${bubble.nerdFont || Qt.application.font.family}">${bubble.icon("check")}</font> copied`
                textFormat: Text.StyledText
                color: theme.accent
                font.pixelSize: 12
                opacity: 0

                SequentialAnimation {
                    id: copied

                    PropertyAction { target: copiedLabel; property: "opacity"; value: 1 }
                    PauseAnimation { duration: 900 }
                    NumberAnimation { target: copiedLabel; property: "opacity"; to: 0; duration: 300; easing.type: Easing.InQuad }
                }
            }
        }
    }

    // A remark's bubble has no keyboard: a click anywhere makes it a normal chat
    // and still reaches what is under it (the input, ×)
    MouseArea {
        anchors.fill: parent
        enabled: bubble.remarking
        onPressed: mouse => {
            bubble.remarking = false;
            bubble.grabKeyboard();
            input.forceActiveFocus();
            mouse.accepted = false;
        }
    }
}
