
override SRCDIR := src
override BUILDDIR := build
override UTILS_DIR := utils
override TARGET = $(BUILDDIR)/mascotd
override PLUGINS_LIB = $(BUILDDIR)/libmascot-plugins.so

override PLUGINS_DIR := $(SRCDIR)/plugins
override PLUGINS_OUT_DIR := $(BUILDDIR)/plugins

override PLUGINS_SUBDIRS := $(notdir $(wildcard $(PLUGINS_DIR)/*))
override PYTHON3 := $(shell which python3)

PREFIX ?= /usr/local

override CFLAGS  += -I$(abspath $(SRCDIR)) -I$(abspath $(BUILDDIR)) -Wall -Wextra -fno-strict-aliasing
override CFLAGS  += $(shell pkg-config --cflags wayland-client)
override LDFLAGS += $(shell pkg-config wayland-client wayland-cursor libarchive --libs) -lm

override WAYLAND_PROTOCOLS_DIR ?= $(shell pkg-config wayland-protocols --variable=pkgdatadir)
override WAYLAND_SCANNER = $(shell pkg-config --variable=wayland_scanner wayland-scanner)

ifeq (,$(WAYLAND_PROTOCOLS_DIR))
$(error Missing wayland-protocols!)
endif
ifeq (,$(WAYLAND_SCANNER))
$(error Missing wayland-scanner!)
endif

override WL_PROTO_DIR := $(BUILDDIR)/wayland-protocols

override WL_HEADERS := \
	$(WL_PROTO_DIR)/cursor-shape-v1.h \
	$(WL_PROTO_DIR)/viewporter.h \
	$(WL_PROTO_DIR)/tablet-v2.h \
	$(WL_PROTO_DIR)/xdg-shell.h \
	$(WL_PROTO_DIR)/fractional-scale-v1.h \
	$(WL_PROTO_DIR)/wlr-layer-shell.h \
	$(WL_PROTO_DIR)/xdg-output.h \
	$(WL_PROTO_DIR)/alpha-modifier-v1.h

override SRC := \
	$(wildcard $(SRCDIR)/*.c) \
	$(wildcard $(SRCDIR)/actions/*.c) \
	$(wildcard $(SRCDIR)/protocol/*.c) \
	$(WL_HEADERS:.h=.c)

override OBJS := $(SRC:$(SRCDIR)/%.c=$(BUILDDIR)/%.o)
override OBJS := $(OBJS:$(WL_PROTO_DIR)/%.c=$(WL_PROTO_DIR)/%.o)

override DEPS := $(OBJS:.o=.d)
override DIRS := $(sort $(BUILDDIR) $(dir $(OBJS)))

override PLUGINS_LIB_SRC := src/plugins.c src/utils.c
override PLUGINS_LIB_OBJS := $(PLUGINS_LIB_SRC:$(SRCDIR)/%.c=$(BUILDDIR)/%.o)

override _ := $(shell mkdir -p $(DIRS))

override WL_PROTO_STAMP := $(WL_PROTO_DIR)/.stamp

# Generate wayland-protocols headers & sources
$(WL_PROTO_STAMP): Makefile wlr-protocols/wlr-layer-shell-unstable-v1.xml
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS_DIR)/staging/cursor-shape/cursor-shape-v1.xml         $(WL_PROTO_DIR)/cursor-shape-v1.h
	$(WAYLAND_SCANNER) private-code  $(WAYLAND_PROTOCOLS_DIR)/staging/cursor-shape/cursor-shape-v1.xml         $(WL_PROTO_DIR)/cursor-shape-v1.c
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS_DIR)/stable/viewporter/viewporter.xml                 $(WL_PROTO_DIR)/viewporter.h
	$(WAYLAND_SCANNER) private-code  $(WAYLAND_PROTOCOLS_DIR)/stable/viewporter/viewporter.xml                 $(WL_PROTO_DIR)/viewporter.c
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS_DIR)/stable/tablet/tablet-v2.xml                      $(WL_PROTO_DIR)/tablet-v2.h
	$(WAYLAND_SCANNER) private-code  $(WAYLAND_PROTOCOLS_DIR)/stable/tablet/tablet-v2.xml                      $(WL_PROTO_DIR)/tablet-v2.c
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS_DIR)/stable/xdg-shell/xdg-shell.xml                   $(WL_PROTO_DIR)/xdg-shell.h
	$(WAYLAND_SCANNER) private-code  $(WAYLAND_PROTOCOLS_DIR)/stable/xdg-shell/xdg-shell.xml                   $(WL_PROTO_DIR)/xdg-shell.c
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS_DIR)/staging/fractional-scale/fractional-scale-v1.xml $(WL_PROTO_DIR)/fractional-scale-v1.h
	$(WAYLAND_SCANNER) private-code  $(WAYLAND_PROTOCOLS_DIR)/staging/fractional-scale/fractional-scale-v1.xml $(WL_PROTO_DIR)/fractional-scale-v1.c
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS_DIR)/unstable/xdg-output/xdg-output-unstable-v1.xml   $(WL_PROTO_DIR)/xdg-output.h
	$(WAYLAND_SCANNER) private-code  $(WAYLAND_PROTOCOLS_DIR)/unstable/xdg-output/xdg-output-unstable-v1.xml   $(WL_PROTO_DIR)/xdg-output.c
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS_DIR)/staging/alpha-modifier/alpha-modifier-v1.xml     $(WL_PROTO_DIR)/alpha-modifier-v1.h
	$(WAYLAND_SCANNER) private-code  $(WAYLAND_PROTOCOLS_DIR)/staging/alpha-modifier/alpha-modifier-v1.xml     $(WL_PROTO_DIR)/alpha-modifier-v1.c
	$(WAYLAND_SCANNER) client-header wlr-protocols/wlr-layer-shell-unstable-v1.xml                             $(WL_PROTO_DIR)/wlr-layer-shell.h
	$(WAYLAND_SCANNER) private-code  wlr-protocols/wlr-layer-shell-unstable-v1.xml                             $(WL_PROTO_DIR)/wlr-layer-shell.c
	@touch $@

.PHONY: protocols-autogen
protocols-autogen: $(WL_PROTO_STAMP)


# Rule to build wayland-protocol sources
$(WL_PROTO_DIR)/%.o: $(WL_PROTO_DIR)/%.c Makefile
	$(CC) $(CFLAGS) -MMD -MF $(patsubst %.o, %.d, $@) -c $< -o $@

# Rule to build generic source files
$(BUILDDIR)/%.o: $(SRCDIR)/%.c Makefile
	$(CC) $(CFLAGS) -MMD -MF $(patsubst %.o, %.d, $@) -c $< -o $@

$(PLUGINS_LIB): $(PLUGINS_LIB_OBJS)
	$(CC) $(CFLAGS) $(PLUGINS_LIB_SRC) -DBUILD_PLUGIN_SUPPORT -I$(BUILDDIR) -fPIC -shared -Wl,-soname,$(notdir $(PLUGINS_LIB)) -lm -o $(PLUGINS_LIB)
	@ln -sf $(notdir $(PLUGINS_LIB)) $(BUILDDIR)/libwayland-shimeji-plugins.so

# Plugins written for wl_shimeji (e.g. the kwinsupport submodule) include <wl_shimeji/plugins.h> and
# link -lwayland-shimeji-plugins: src/compat provides the header, and the symlink above the library.
# Its soname keeps libmascot-plugins.so as the runtime dependency, and the rpath finds it in
# $(PREFIX)/lib from $(PREFIX)/lib/mascot without LD_LIBRARY_PATH.
$(PLUGINS_SUBDIRS): $(PLUGINS_LIB)
	@echo "-> Building plugin $@..."
	$(MAKE) -s -C $(PLUGINS_DIR)/$@ BUILDDIR="$(abspath $(BUILDDIR))" PLUGINS_OUT_DIR="$(abspath $(PLUGINS_OUT_DIR))" CFLAGS="$(CFLAGS) -I$(abspath $(SRCDIR)/compat) -I$(DESTDIR)$(PREFIX)/include/" LDFLAGS="$(LDFLAGS) -L$(abspath $(BUILDDIR)) -Wl,-rpath,'\$$\$$ORIGIN/..'"

.PHONY: build-plugins
build-plugins: $(PLUGINS_SUBDIRS)

# Rule to build the binary
$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@

# Rule to build mascot
# py-compose inlines every module client.py imports, so any of them changes the output
$(UTILS_DIR)/mascot: $(SRCDIR)/mascotctl/client.py $(shell find $(SRCDIR)/mascotctl -name "*.py")
	@mkdir -p $(UTILS_DIR)
	$(PYTHON3) scripts/py-compose.py -s $< -o $@

$(WL_HEADERS) $(WL_HEADERS:.h=.c) $(OBJS): | $(WL_PROTO_STAMP)

.PHONY: all
all: $(TARGET) $(PLUGINS_LIB) $(UTILS_DIR)/mascot

.PHONY: clean
clean:
	@-rm -rf $(TARGET) $(PLUGINS_LIB) $(BUILDDIR) $(UTILS_DIR)/mascot $(UTILS_DIR)

# The bubble's read-only tools (tools/bin/<tool> links to tools/mascot-tools)
TOOLS := get_current_weather list_directory read_file search_file look_at_image list_todos add_todo remove_todo edit_todo \
	set_reminder list_reminders cancel_reminder due_reminders last_commands sleep_mode context_size check_system read_log

.PHONY: install
install: all
	install -d $(DESTDIR)$(PREFIX)/bin/
	install -m755 $(TARGET) $(DESTDIR)$(PREFIX)/bin/
	install -m755 $(UTILS_DIR)/mascot $(DESTDIR)$(PREFIX)/bin/mascot
	install -d $(DESTDIR)$(PREFIX)/share/systemd/user/
	install -m644 systemd/mascotd.socket $(DESTDIR)$(PREFIX)/share/systemd/user/
	sed 's|@BINDIR@|$(PREFIX)/bin|g' systemd/mascotd.service > $(DESTDIR)$(PREFIX)/share/systemd/user/mascotd.service
	chmod 644 $(DESTDIR)$(PREFIX)/share/systemd/user/mascotd.service
	install -d $(DESTDIR)$(PREFIX)/lib/
	install -m755 $(PLUGINS_LIB) $(DESTDIR)$(PREFIX)/lib/
	install -d $(DESTDIR)$(PREFIX)/include/
	install -d $(DESTDIR)$(PREFIX)/include/mascot
	install -m644 src/plugins.h $(DESTDIR)$(PREFIX)/include/mascot/plugins.h
	install -m644 src/master_header.h $(DESTDIR)$(PREFIX)/include/mascot/master_header.h
	install -d $(DESTDIR)$(PREFIX)/share/mascot/ui/
	install -m644 ui/*.qml ui/prompt.md $(DESTDIR)$(PREFIX)/share/mascot/ui/
	install -d $(DESTDIR)$(PREFIX)/share/mascot/tools/bin/
	install -m755 tools/mascot-tools $(DESTDIR)$(PREFIX)/share/mascot/tools/
	install -m644 tools/functions.json $(DESTDIR)$(PREFIX)/share/mascot/tools/
	for tool in $(TOOLS); do ln -sfn ../mascot-tools $(DESTDIR)$(PREFIX)/share/mascot/tools/bin/$$tool; done
	install -d $(DESTDIR)$(PREFIX)/share/mascot/prototypes/
	cp -R --no-preserve=ownership prototypes/. $(DESTDIR)$(PREFIX)/share/mascot/prototypes/
	chmod -R u=rwX,go=rX $(DESTDIR)$(PREFIX)/share/mascot/prototypes/

# Removes only what install/install-plugins put there; directories are removed
# only if empty, since $(PREFIX)/share/mascot is also the data root when PREFIX=~/.local
.PHONY: uninstall
uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/mascotd
	rm -f $(DESTDIR)$(PREFIX)/bin/mascot
	rm -f $(DESTDIR)$(PREFIX)/share/systemd/user/mascotd.socket
	rm -f $(DESTDIR)$(PREFIX)/share/systemd/user/mascotd.service
	rm -f $(DESTDIR)$(PREFIX)/lib/libmascot-plugins.so
	rm -f $(DESTDIR)$(PREFIX)/lib/mascot/*.so
	rm -f $(DESTDIR)$(PREFIX)/include/mascot/plugins.h
	rm -f $(DESTDIR)$(PREFIX)/include/mascot/master_header.h
	rm -f $(DESTDIR)$(PREFIX)/share/mascot/ui/Bubble.qml
	rm -f $(DESTDIR)$(PREFIX)/share/mascot/ui/shell.qml
	rm -f $(DESTDIR)$(PREFIX)/share/mascot/ui/Menu.qml
	rm -f $(DESTDIR)$(PREFIX)/share/mascot/ui/prompt.md
	rm -f $(DESTDIR)$(PREFIX)/share/mascot/tools/mascot-tools $(DESTDIR)$(PREFIX)/share/mascot/tools/functions.json
	for tool in $(TOOLS); do rm -f $(DESTDIR)$(PREFIX)/share/mascot/tools/bin/$$tool; done
	rm -rf $(DESTDIR)$(PREFIX)/share/mascot/prototypes
	rmdir $(DESTDIR)$(PREFIX)/lib/mascot $(DESTDIR)$(PREFIX)/include/mascot \
		$(DESTDIR)$(PREFIX)/share/mascot/ui $(DESTDIR)$(PREFIX)/share/mascot/tools/bin \
		$(DESTDIR)$(PREFIX)/share/mascot/tools $(DESTDIR)$(PREFIX)/share/mascot 2>/dev/null || true

.PHONY: install-plugins
install-plugins: build-plugins
	install -d $(DESTDIR)$(PREFIX)/lib/mascot/
	install -m 0755 "$(PLUGINS_OUT_DIR)/"*.so "$(DESTDIR)$(PREFIX)/lib/mascot/"

# Handle header dependency rebuild
sinclude $(DEPS)

.DEFAULT_GOAL := all
