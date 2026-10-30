.pragma library

// Which model gets the file, todo and shell tools: only one whose answers are made on this computer, so
// what the tools read stays here. An ollama: model counts, unless Ollama is on another machine
// (OLLAMA_HOST) or it is one of Ollama's cloud models (…-cloud, …:cloud), which run at ollama.com

// Whether OLLAMA_HOST (empty: Ollama's own default) is this computer
function ollamaHere(host) {
    // The host as Ollama finds it in a URL: after the scheme and any user@, before the path and the port
    let address = host.trim().replace(/^[a-z][a-z0-9+.-]*:\/\//i, "").split(/[\/?#]/)[0];
    address = address.slice(address.lastIndexOf("@") + 1);
    const name = address.startsWith("[") ? address.slice(1, address.indexOf("]")) : address.replace(/:\d*$/, "");
    return name === "" || name === "localhost" || name === "::1" || name === "0.0.0.0"
        || /^127(\.\d{1,3}){3}$/.test(name);
}

// The local model in aichat --info's "model: ollama:<name>" line, or "" if it is not local
function localModel(info, host) {
    const m = info.match(/^model:?\s+ollama:(\S+)/m);
    if (!m || /[-:]cloud$/.test(m[1]) || !ollamaHere(host))
        return "";
    return m[1];
}

// The config file aichat --info says it reads ("config_file  <path>"), or "": CHAT_COMMAND may give it another one,
// and where that sends an ollama: model is what counts
function configFile(info) {
    const m = info.match(/^config_file\s+(.*\S)\s*$/m);
    return m ? m[1] : "";
}
