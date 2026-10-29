-- Minimal config for a nested Hyprland (0.57+, Lua): Hyprland -c hyprland.lua
hl.monitor({
    output   = "",
    mode     = "1600x900",
    position = "auto",
    scale    = 1,
})

hl.config({
    misc = {
        force_default_wallpaper = 0,
        disable_hyprland_logo   = true,
        disable_splash_rendering = true,
    },
    animations = {
        enabled = false,
    },
    ecosystem = {
        no_donation_nag = true,
    },
})
