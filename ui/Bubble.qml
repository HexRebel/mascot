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

    // The mascot plays its "Talk" behavior while a reply streams (not for dot commands)
    signal talked(int mascot, bool active)
    readonly property bool talking: visible && !!current?.job && current.replying
    onTalkingChanged: if (bubble.event)
        bubble.talked(bubble.event.mascot, bubble.talking)

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
            // (the model's answer), "remark" (what the mascot said on its own) or
            // "system" (the bubble's own notes and dot command output), each
            // drawn in its own pywal colour
            property ListModel entries: ListModel {}
            property int streaming: -1 // entry the running command writes into
            property var job: null // the running command, see run()
            property bool replying: false // job answers a message, not a dot command
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
            bubble.conversations[mascot] = conversationComponent.createObject(bubble);
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
        if (e.remark) {
            bubble.remark(e);
            return;
        }
        bubble.remarking = false;
        bubble.keepKeyboard = bubble.fromKey;
        bubble.fromKey = false;
        // Double clicks arrive as two taps: keep the open conversation
        if (bubble.visible && bubble.event && bubble.event.mascot === e.mascot) {
            bubble.grabKeyboard();
            input.forceActiveFocus();
            return;
        }

        bubble.event = e;
        bubble.current = conversation(e.mascot);
        input.text = "";
        bubble.grabKeyboard(); // before showing it, so it maps with the keyboard
        bubble.visible = true;
        input.forceActiveFocus();
    }

    // CHAT_REMARKS: the mascot says something on its own. The bubble opens
    // without the keyboard (Hyprland gives an OnDemand layer surface the
    // keyboard when it maps, so it has none) and closes 7 s after the remark is
    // written, unless the pointer is on it; a click makes it a normal chat
    property bool remarking: false

    function remark(e: var): void {
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
            + "Write in the language of your earlier conversation, if any, else in the language of the locale "
            + `${Qt.locale().name}. Do not mention this note.)`, "remark");
    }

    Timer {
        interval: 7000
        running: bubble.remarking && bubble.visible && !bubble.busy && !remarkHover.hovered
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
        bubble.conversations[e.to] = conversation(e.mascot);
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
        bubble.remarking = false; // after hiding, or OnDemand would take the keyboard first
        bubble.keepKeyboard = false;
    }

    function close(): void {
        bubble.dismiss();
        if (bubble.event)
            bubble.released(bubble.event.mascot);
    }

    // aichat's REPL dot commands need a tty, so the bubble emulates the useful
    // ones with aichat's CLI flags. .model, .role and .session apply to this
    // mascot's conversation until changed
    function chosen(): QtObject {
        return bubble.current;
    }

    readonly property string helpText: [
        ".info                  show aichat's settings",
        ".models / .roles / .sessions   list them",
        ".model <name>          switch model (e.g. openrouter:…)",
        ".role <name>           switch role (instead of the default)",
        ".session <name>        start/continue a session with memory",
        ".exit model|session    go back to the default",
        ".exit role             leave the role (also the default one)",
        ".mascots               list the mascots you have",
        ".mascot <name>         swap this mascot for another one",
        ".tools                 list what the mascot can look up",
        ".todo                  show the todo list",
        ".todo add <item>       add to it",
        ".todo done <n|text>    remove an item (by number or text)",
        ".copy                  copy the last answer",
        ".clear                 start this conversation over",
        "",
        "Select text with the mouse and press Ctrl+C to copy part of it."
    ].join("\n")

    function roleFlags(): var {
        const c = chosen();
        const role = c.role || (c.noRole ? "" : bubble.event.role);
        if (role)
            return ["-r", role]; // only ever one -r: aichat refuses two
        if (bubble.prompt)
            return ["--prompt", bubble.prompt.replace(/\{name\}/g, bubble.event?.prototype || "a desktop mascot")];
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
    // the daemon is older. MASCOT_MEMORY_LIMIT (characters) overrides it, for testing
    readonly property int memoryLimit: parseInt(Quickshell.env("MASCOT_MEMORY_LIMIT"))
        || (bubble.event?.memory === 0 ? 0 : (bubble.event?.memory ?? 8000) * 3)

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
        files: ["list_directory", "read_file"],
        todo: ["list_todos", "add_todo", "remove_todo"]
    })
    // Only with a local model, so what they read stays on this computer
    readonly property var localTools: ["files", "todo"]
    readonly property string toolsDir: Quickshell.shellPath("../tools")
    // One list for all mascots, in Markdown ("- [ ] item"), kept in the data directory
    readonly property string todoFile: `${bubble.dataDir}/todo.md`

    function toolNames(): var {
        return (bubble.event?.tools ?? "").split(",").map(t => t.trim().toLowerCase())
            .filter((t, i, all) => t in bubble.toolFunctions && all.indexOf(t) === i);
    }

    // The environment that gives aichat these tools; local: whether the model
    // is local, so localTools are among them (tools/mascot-tools also refuses
    // them without it)
    function toolEnvironment(tools: var, local: bool): var {
        // No flatMap in Qt's JavaScript engine
        const names = [].concat(...tools.filter(t => local || !bubble.localTools.includes(t)).map(t => bubble.toolFunctions[t]));
        if (!names.length)
            return { AICHAT_FUNCTION_CALLING: "false" };
        return {
            AICHAT_FUNCTIONS_DIR: bubble.toolsDir,
            AICHAT_FUNCTION_CALLING: "true",
            AICHAT_USE_TOOLS: names.join(","),
            MASCOT_TOOLS_LOCAL: local ? "1" : "0",
            MASCOT_TODO_FILE: bubble.todoFile
        };
    }

    // Runs one of Mascot's tools itself, not through the model (.todo); its
    // output is written into the conversation
    function runTool(name: string, args: var): void {
        const path = `${bubble.toolsDir}/bin/${name}`.replace(/'/g, "'\\''");
        run([JSON.stringify(args)], false, "system", null, bubble.current, `'${path}'`,
            { MASCOT_TOOLS_LOCAL: "1", MASCOT_TODO_FILE: bubble.todoFile });
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
    // (ollama:…) answers, so what they read stays on this computer, and never to a .session (it
    // outlives Mascot): aichat --info on a fresh session says which model that
    // is, as .model and the role may each choose it
    function withTools(c: QtObject, command: string, done: var): void {
        const tools = toolNames();
        const role = roleFlags();
        if (!tools.length) {
            done(role, toolEnvironment([], false));
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
                // Models like to say they noted something without doing it
                const todo = env.AICHAT_USE_TOOLS.includes("add_todo") ? "\n\nYou keep the user's todo list with the "
                    + "tools list_todos, add_todo and remove_todo. When the user wants something on it, off it or looked "
                    + "up, call the tool; never say you added or removed something without calling it." : "";
                done(model.concat(`--prompt=---\n${front.join("\n")}\n---\n${prompt}${todo}`), env);
            };
            if (!tools.some(t => bubble.localTools.includes(t)) || c.session) {
                send(false);
                return;
            }
            const probe = (c.model ? ["-m", c.model] : []).concat(role, "-s", "mascot-probe");
            lookup(probe, c, command, (info, ok) => send(ok && /^model:?\s+ollama:/m.test(info)));
        };
        if (role[0] !== "-r") {
            build([], role[1] ?? ""); // Mascot's prompt, or none
            return;
        }
        // "---\n<front matter>\n---\n\n<prompt>"
        lookup(role, c, command, (info, ok) => {
            if (!ok) {
                done(role, toolEnvironment([], false)); // aichat says why with the message
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
        const command = bubble.event?.command || "aichat";
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
                const local = /read_file|list_todos/;
                c.entries.append({ kind: "system", body: local.test(c.persona) && !local.test(key)
                    ? "not a local model - no files or todo list, and the memory starts over, so what the mascot read stays here"
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
    // sums the memory up first if it has grown past memoryLimit
    function remember(text: string, kind: string, c: QtObject, command: string, base: var, env: var): void {
        const post = message => {
            c.memoryChars += message.length;
            run(base.concat("-s", c.memory, "--save-session", "--", message), true, kind, null, c, command, env);
        };
        if (!bubble.memoryLimit || c.memoryChars <= bubble.memoryLimit) {
            post(text);
            return;
        }
        say("summing up the memory…");
        run(base.concat("-s", c.memory, "--", "(Not from the user: sum up our conversation so far in a few short "
            + "sentences, for your own memory - names, facts, what we talked about and how. Write only the "
            + "summary, in the language of the conversation.)"), false, "", (summary, ok) => {
            // Failed: carry on in the long memory rather than lose it
            if (ok && summary.trim()) {
                c.memory = `chat-${++bubble.memoryCount}`;
                c.memoryChars = 0;
                text = `(What we talked about before, summed up: ${summary.trim()})\n\n${text}`;
            }
            post(text);
        }, c, command, toolEnvironment([], false));
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
        return bubble.prompt ? "none (Mascot's prompt)" : "none (aichat's default)";
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
                const c = chosen();
                if (arg) {
                    c[key] = arg;
                    if (key === "role")
                        c.noRole = false;
                }
                say(`${key}: ${c[key] || defaultName(key)}`);
                return;
            }
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
                    say("tools: none (set CHAT_TOOLS to time, weather and/or files)");
                    return;
                }
                const notes = {
                    time: "time - the date and time, sent with every message",
                    weather: "weather - from wttr.in (only the place name is sent)",
                    files: "files - lists and reads files in your home directory, never hidden ones, "
                        + "and only with a local (ollama:) model" + (chosen().session ? "; not in a .session" : ""),
                    todo: "todo - shows, adds to and removes from your todo list (also .todo), "
                        + "only with a local (ollama:) model" + (chosen().session ? "; not in a .session" : "")
                };
                say(tools.map(t => notes[t]).join("\n"));
                return;
            }
        case ".todo":
            {
                const [sub, ...words] = rest;
                const item = words.join(" ");
                const tool = !sub ? "list_todos" : sub === "add" ? "add_todo"
                    : ["done", "remove", "rm"].includes(sub) ? "remove_todo" : "";
                if (!tool || (sub && !item))
                    say("use .todo, .todo add <item> or .todo done <number or text>");
                else
                    runTool(tool, sub ? { item: item } : {});
                return;
            }
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
                }
            }
            stderr: StdioCollector {
                id: jobErrors
            }

            onExited: (exitCode, exitStatus) => {
                const c = job.conv;
                if (c?.job === job) { // not stopped
                    if (exitCode !== 0 && !job.done)
                        c.error = jobErrors.text.trim() || `The command failed (exit ${exitCode})`;
                    if (c.replying && c.streaming >= 0 && c.streaming < c.entries.count)
                        c.memoryChars += c.entries.get(c.streaming).body.length;
                    // What Mascot's tools really changed (they say so on stderr),
                    // whatever the reply claims
                    if (c.replying) {
                        for (const line of jobErrors.text.split("\n")) {
                            if (line.startsWith("mascot-tools: "))
                                c.entries.append({ kind: "system", body: "✓ " + line.slice(14) });
                        }
                    }
                    c.job = null;
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

                // Follow the streamed answer
                onImplicitHeightChanged: scroller.contentY = Math.max(0, implicitHeight - scroller.height)

                Repeater {
                    model: bubble.entries

                    TextEdit {
                        id: entry

                        required property string kind
                        required property string body
                        required property int index

                        // Reasoning models write <think>…</think> before the answer: hide it,
                        // and say "thinking…" until the answer starts
                        readonly property bool answering: kind === "reply" || kind === "remark"
                        readonly property string answer: answering ? bubble.answerOf(body) : body.trim()
                        readonly property bool thinking: answering && answer === "" && /<think/.test(body)
                            && bubble.current.streaming === index && !!bubble.current.job

                        width: log.width
                        visible: text !== "" // a command that has printed nothing yet
                        text: thinking ? "thinking…" : (kind === "you" ? "› " : "") + answer
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
                        color: thinking ? theme.muted : kind === "you" ? theme.accent : kind === "reply" ? theme.foreground
                            : kind === "remark" ? theme.remark : theme.muted
                        font.pixelSize: 13
                    }
                }
            }
        }

        Text {
            width: parent.width
            visible: !!bubble.current?.error
            text: bubble.current?.error ?? ""
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
