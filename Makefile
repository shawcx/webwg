
all:
	@make -C src

run:
	python3 -m webwg

clean:
	@make -C src clean
	@find . -type d -name __pycache__ -exec rm -rfv {} +

distclean: clean
	@make -C src distclean
	@rm -rvf build dist WebWG.egg-info
