/*
    wl_shimeji/plugins.h - compatibility header for plugins written for wl_shimeji

    Mascot is a fork of wl_shimeji; its plugin ABI is the same apart from the names.
    Plugins such as the kwinsupport submodule include <wl_shimeji/plugins.h> and use
    the old version macro. mascotd also looks up their wl_shimeji_plugin_* symbols.

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 2
    of the License, or (at your option) any later version.
*/

#ifndef MASCOTD_COMPAT_WL_SHIMEJI_PLUGINS_H
#define MASCOTD_COMPAT_WL_SHIMEJI_PLUGINS_H

#include "../../plugins.h"

#define WL_SHIMEJI_PLUGIN_TARGET_VERSION MASCOTD_PLUGIN_TARGET_VERSION

#endif
