
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

CSS_OUT = $(STATIC_ROOT)/css/webwg.css
CSS_SRC = sass/webwg.scss $(wildcard sass/*.scss)

SASS_FLAGS = -I ./node_modules/@fortawesome/fontawesome-pro/scss \
             -I ./node_modules/bootstrap/scss

WEBFONTS_SRC = ./node_modules/@fortawesome/fontawesome-pro/webfonts
WEBFONTS = $(STATIC_ROOT)/webfonts

all: node_modules $(JS_OUT) $(JOIN_OUT) $(CSS_OUT) $(WEBFONTS) $(CLIWG_OUT)
	@#

$(WEBFONTS): $(WEBFONTS_SRC)
	@cp -r $(WEBFONTS_SRC) $(STATIC_ROOT)

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

$(CSS_OUT): $(CSS_SRC)
	@echo sass $< '=>' $@
	@$(SASS) $(SASS_FLAGS) $< $@

clean:

distclean: clean
	@rm -vf $(CSS_OUT)
	@rm -vf $(JS_OUT)
	@rm -vf $(JOIN_OUT)
	@rm -vf $(CLIWG_OUT)
	@rm -rf node_modules
