{
  lib,
  stdenv,
  pkg-config,
  wayland,
  wayland-protocols,
  wayland-scanner,
  libarchive,
  uthash,
  python3,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "mascot-unwrapped";
  version = "0-unstable";

  src = builtins.path { path = ./..; };

  nativeBuildInputs = [
    pkg-config
    wayland
    wayland-protocols
    wayland-scanner
    libarchive
    uthash
    python3
  ];

  makeFlags = [
    "PREFIX=$(out)"
  ];

  preBuild = ''
    substituteInPlace ./Makefile \
    --replace-fail "\$(shell which python3)" "${lib.getExe python3}"
  '';

  meta = {
    description = "Shimeji reimplementation for Wayland in C.";
    homepage = "https://github.com/CluelessCatBurger/wl_shimeji";
    mainProgram = "mascot";
    license = lib.licenses.gpl2Only;
    platforms = lib.platforms.linux;
    maintainers = with lib.maintainers; [ claymorwan ];
  };
})
