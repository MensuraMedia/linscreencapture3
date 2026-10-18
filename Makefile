ICON_SRC ?= $(HOME)/projects/assets/icons/regular
RESOURCE  = linscreencapture/linscreencapture.gresource
# Uses Xvfb when available, else the live display.
HEADLESS := $(shell command -v xvfb-run >/dev/null 2>&1 && echo 'xvfb-run -a -s "-screen 0 1600x1000x24"')

.PHONY: icons resources run test snapshot clean launcher unlauncher install uninstall deb

icons:
	python3 tools/sync_icons.py --source "$(ICON_SRC)"
	$(MAKE) resources

resources:
	glib-compile-resources --target $(RESOURCE) --sourcedir data --sourcedir linscreencapture/ui data/linscreencapture.gresource.xml

run: resources
	python3 -m linscreencapture

test: resources
	$(HEADLESS) python3 -m pytest -q

snapshot: resources
	$(HEADLESS) python3 tools/snapshot_shell.py

clean:
	rm -f $(RESOURCE)

# User-level menu entry "LinScreenCapture3" that runs this checkout (no install needed). It is named after the
# application id so Alt+Tab, the panel and the window list match the window (WM_CLASS) to it and its icon.
APP_ID = com.mensuramedia.LinScreenCapture
APPS   = $(HOME)/.local/share/applications
ICONS  = $(HOME)/.local/share/icons/hicolor
SIZES  = 16 24 32 48 64 128 256 512
launcher: resources
	mkdir -p $(APPS) $(ICONS)/scalable/apps
	sed "s|@ROOT@|$(CURDIR)|g" data/linscreencapture3-dev.desktop.in > $(APPS)/$(APP_ID).desktop
	rm -f $(APPS)/linscreencapture3.desktop $(ICONS)/*/apps/linscreencapture3.png
	cp data/icons/hicolor/scalable/apps/$(APP_ID).svg $(ICONS)/scalable/apps/
	for s in $(SIZES); do mkdir -p $(ICONS)/$${s}x$${s}/apps; cp resources/icons/linscreencapture-$$s.png $(ICONS)/$${s}x$${s}/apps/$(APP_ID).png; done
	-update-desktop-database $(APPS) 2>/dev/null
	-gtk-update-icon-cache -q -t -f $(ICONS) 2>/dev/null
	@echo "Menu entry installed: $(APPS)/$(APP_ID).desktop"

unlauncher:
	rm -f $(APPS)/$(APP_ID).desktop $(APPS)/linscreencapture3.desktop $(ICONS)/scalable/apps/$(APP_ID).svg
	for s in $(SIZES); do rm -f $(ICONS)/$${s}x$${s}/apps/$(APP_ID).png $(ICONS)/$${s}x$${s}/apps/linscreencapture3.png; done
	-update-desktop-database $(APPS) 2>/dev/null

# Installation (see INSTALL.md): ./install.sh for this user, sudo-backed --system for everyone, or the .deb.
install:
	./install.sh

uninstall:
	./install.sh --uninstall

deb: resources
	packaging/build-deb.sh
