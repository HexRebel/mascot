{
  lib,
  symlinkJoin,
  python3,
  python3Packages,
  mascot-unwrapped,
}:

symlinkJoin {
  pname = "mascot";
  inherit (mascot-unwrapped) version;

  paths = [
    mascot-unwrapped
  ];

  nativeBuildInputs = [
    python3Packages.wrapPython
  ];

  pythonInputs = with python3Packages; [
    pillow
  ];

  postBuild = ''
    buildPythonPath "$pythonInputs"

    wrapProgram $out/bin/mascot \
      --prefix PATH : $program_PATH \
      --set PYTHONHOME ${python3} \
      --set PYTHONPATH $program_PYTHONPATH
  '';

  meta = mascot-unwrapped.meta // {
    hydraPlatforms = [ ];
    priority = (mascot-unwrapped.meta.priority or lib.meta.defaultPriority) - 1;
  };
}
