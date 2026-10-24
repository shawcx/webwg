
all:
	@make -C src

# builds dist/*.deb for Debian 13+ and Ubuntu 25.04+ in a debian:trixie container,
# starting from a clean webwg/static so nothing stale ends up in the package
DEB_IMAGE = debian:trixie
DEB_BUILD_DEPS = build-essential debhelper dh-python pybuild-plugin-pyproject python3-all \
                 python3-setuptools python3-wheel curl ca-certificates lintian

deb:
	rm -rf webwg/static
	@make -C src
	mkdir -p dist
	docker run --rm -v $(CURDIR):/src:ro -v $(CURDIR)/dist:/out $(DEB_IMAGE) sh -c '\
		apt-get update -qq && \
		apt-get install -qq -y --no-install-recommends $(DEB_BUILD_DEPS) >/dev/null && \
		/src/packaging/build-debs /out; status=$$?; \
		chown -R $(shell id -u):$(shell id -g) /out; exit $$status'

run: all
	python3 -m webwg --debug

clean:
	@make -C src clean
	@find . -type d -name __pycache__ -exec rm -rfv {} +

distclean: clean
	@make -C src distclean
	@rm -rvf build dist *.egg-info
