build:
	pipenv run pyinstaller build.spec --onefile --windowed

clean:
	rm -rf build/
	rm -rf dist/

buildclean:
	make clean
	make build
