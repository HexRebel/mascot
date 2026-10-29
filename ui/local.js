.pragma library

// Which model gets the file, todo and shell tools: only one whose answers are made on this computer, so
// what the tools read stays here. An ollama: model counts, unless Ollama is on another machine
// (OLLAMA_HOST) or it is one of Ollama's cloud models (…-cloud, …:cloud), which run at ollama.com

// Whether OLLAMA_HOST (empty: Ollama's own default) is this computer
function ollamaHere(host) {
    const address = host.replace(/^[a-z]+:\/\//i, "").replace(/\/.*$/, "");
    const name = address.startsWith("[") ? address.slice(1, address.indexOf("]")) : address.replace(/:\d*$/, "");
    return name === "" || name === "localhost" || name === "::1" || name === "0.0.0.0" || /^127\./.test(name);
}

// The local model in aichat --info's "model: ollama:<name>" line, or "" if it is not local
function localModel(info, host) {
    const m = info.match(/^model:?\s+ollama:(\S+)/m);
    if (!m || /[-:]cloud$/.test(m[1]) || !ollamaHere(host))
        return "";
    return m[1];
}
