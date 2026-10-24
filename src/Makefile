
PATH := $(PATH):/opt/homebrew/bin

SASS       = ./node_modules/.bin/sass
BROWSERIFY = ./node_modules/.bin/browserify

STATIC_ROOT = ../webwg/static

JS_FILES := $(wildcard js/*.js)
JS_FILES := $(JS_FILES) $(wildcard js/records/*.js)
JS_FILE   = js/webwg.js
JS_OUT    = $(STATIC_ROOT)/$(JS_FILE)

# the public join page gets its own small bundle
JOIN_FILE = js/join.js
JOIN_OUT  = $(STATIC_ROOT)/$(JOIN_FILE)

CLIWG_OUT = $(STATIC_ROOT)/cliwg.py

# images/icon.svg is the source, make icons redraws the favicon and touch icon
ICONS = $(addprefix $(STATIC_ROOT)/,icon.svg favicon.ico apple-touch-icon.png)

CSS_OUT = $(STATIC_ROOT)/css/webwg.css
CSS_SRC = sass/webwg.scss $(wildcard sass/*.scss)

SASS_FLAGS = -I ./node_modules/@fortawesome/fontawesome-pro/scss \
             -I ./node_modules/bootstrap/scss

WEBFONTS_SRC = ./node_modules/@fortawesome/fontawesome-pro/webfonts
WEBFONTS = $(STATIC_ROOT)/webfonts

# latin IBM Plex, served from here so pages need nothing outside this server
PLEX      = ./node_modules/@fontsource/ibm-plex
FONTS_SRC = $(addprefix $(PLEX)-sans/files/ibm-plex-sans-latin-,400-normal.woff2 500-normal.woff2 600-normal.woff2) \
            $(addprefix $(PLEX)-mono/files/ibm-plex-mono-latin-,400-normal.woff2 500-normal.woff2)
FONTS     = $(STATIC_ROOT)/fonts

all: node_modules $(JS_OUT) $(JOIN_OUT) $(CSS_OUT) $(WEBFONTS) $(FONTS) $(CLIWG_OUT) $(ICONS)
	@#

$(WEBFONTS): $(WEBFONTS_SRC)
	@cp -r $(WEBFONTS_SRC) $(STATIC_ROOT)

$(FONTS): $(FONTS_SRC)
	@mkdir -p $@
	@cp $^ $@
	@touch $@

node_modules:
	@npm install .

$(JS_OUT): $(JS_FILES)
	@echo browserify $(JS_FILE) '=>' $@
	@$(BROWSERIFY) $(JS_FILE) -o $@

$(JOIN_OUT): $(JOIN_FILE) js/wgkeys.js
	@echo browserify $(JOIN_FILE) '=>' $@
	@$(BROWSERIFY) $(JOIN_FILE) -o $@

$(CLIWG_OUT): ../cliwg.py
	@cp -v $< $@

$(ICONS): $(STATIC_ROOT)/%: images/%
	@cp -v $< $@

# needs rsvg-convert (librsvg2-bin) and ImageMagick, the results are committed
icons: images/icon.svg images/icon-16.svg
	rsvg-convert -w 16 -h 16 images/icon-16.svg -o images/16.png
	rsvg-convert -w 32 -h 32 images/icon.svg -o images/32.png
	rsvg-convert -w 48 -h 48 images/icon.svg -o images/48.png
	convert images/16.png images/32.png images/48.png images/favicon.ico
	sed 's/rx="14"/rx="0"/' images/icon.svg | rsvg-convert -w 180 -h 180 -o images/apple-touch-icon.png
	@rm images/16.png images/32.png images/48.png

$(CSS_OUT): $(CSS_SRC)
	@echo sass $< '=>' $@
	@$(SASS) $(SASS_FLAGS) $< $@

.PHONY: icons clean distclean

clean:

distclean: clean
	@rm -vf $(CSS_OUT)
	@rm -vf $(JS_OUT)
	@rm -vf $(JOIN_OUT)
	@rm -vf $(CLIWG_OUT)
	@rm -rvf $(FONTS)
	@rm -vf $(ICONS)
	@rm -rf node_modules
