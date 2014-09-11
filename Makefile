CUR_BRANCH = $(shell git branch | sed -n -e 's,^\*[[:blank:]]*,,p')

unittest:
	python -m unittest discover --start-directory pyhard2/driver --pattern '*.py'

unittestdoc:
	python -m unittest discover --start-directory documentation --pattern '*.py'

doctest:
	python -m doctest pyhard2/pid.py
	python -m doctest pyhard2/driver/__init__.py
	python -m doctest pyhard2/driver/ieee/scpi.py

test: unittest doctest

distribute:
	python setup.py sdist --formats=gztar,zip

doc: unittestdoc
	-mkdir -p documentation/gv
	PYTHONPATH="." python documentation/gen_tree_graphs.py
	PYTHONPATH="." sphinx-build -w tmp/sphinx.out -b html documentation html

doc-img:
	plantuml sphinx/driver_api.txt
	plantuml sphinx/proxy_api.txt

upload-doc:
	rsync --archive --verbose --partial --progress -e ssh\
	   	html/ mathias_laurin@web.sourceforge.net:/home/project-web/pyhard2/htdocs/

export:
	git archive $(CUR_BRANCH) --format=zip > /Users/laurin/Desktop/pyhard2-code.zip

rcc:
	pyrcc4 -o pyhard2/rsc/__init__.py pyhard2/rsc/resources.qrc

lint:
	pylint --disable=C0103 pyhard2

sloccount:
	sloccount --wide --details -- pyhard2

virtual-conf:
	gsed -r 's/^( *driver:).*$$/\1 virtual/g' circat.yml > virtual-circat.yml

