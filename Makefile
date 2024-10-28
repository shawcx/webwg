
all:
	@make -C src

deb: all
	python3 setup.py --command-packages=stdeb.command bdist_deb

run: all
	python3 -m webwg --debug

clean:
	@make -C src clean
	@find . -type d -name __pycache__ -exec rm -rfv {} +

distclean: clean
	@make -C src distclean
	@rm -rvf build dist WebWG.egg-info
