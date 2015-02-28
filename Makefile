CUR_BRANCH = $(shell git branch | sed -n -e 's,^\*[[:blank:]]*,,p')

unittest:
	python3.4 -m unittest discover --start-directory pyhard2 --pattern '*.py'

unittestdoc:
	python3.4 -m unittest discover --start-directory documentation --pattern '*.py'

doctest:
	python3.4 -m doctest pyhard2/pid.py
	python3.4 -m doctest pyhard2/driver/__init__.py
	python3.4 -m doctest pyhard2/driver/ieee/scpi.py

test: unittest doctest

distribute:
	python3.4 setup.py sdist --formats=gztar,zip

doc: unittestdoc doc-img
	-mkdir -p documentation/gv
	PYTHONPATH="." python3.4 documentation/gen_tree_graphs.py
	PYTHONPATH="." sphinx-build -w tmp/sphinx.out -b html documentation html

doc-img:
	plantuml sphinx/driver_api.txt
	plantuml sphinx/proxy_api.txt

upload-doc:
	rsync --archive --verbose --partial --progress -e ssh\
	   	html/ mathias_laurin@web.sourceforge.net:/home/project-web/pyhard2/htdocs/

pdf:
	-rm -r latex
	mkdir latex
	PYTHONPATH="." sphinx-build -w tmp/sphinx.out -b latex documentation latex
	-cd latex && make all; make all; cp pyhard2.pdf ..
	rm -r latex

export:
	git archive $(CUR_BRANCH) --format=zip > /Users/laurin/Desktop/pyhard2-code.zip

rcc:
	pyrcc5 -o pyhard2/rsc/__init__.py pyhard2/rsc/resources.qrc

lint:
	pylint --disable=C0103 pyhard2

sloccount:
	sloccount --wide --details -- pyhard2

virtual-conf:
	gsed -r 's/^( *driver:).*$$/\1 virtual/g' circat.yml > virtual-circat.yml

