
all:
	@make -C src

run: all
	/opt/webwg/bin/python3 -m webwg --debug

clean:
	@make -C src clean
	@find . -type d -name __pycache__ -exec rm -rfv {} +

distclean: clean
	@make -C src distclean
	@rm -rvf build dist WebWG.egg-info
