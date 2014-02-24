CUR_BRANCH = $(shell git branch | sed -n -e 's,^\*[[:blank:]]*,,p')

distribute:
	python setup.py sdist --formats=gztar,zip

doc:
	PYTHONPATH="." sphinx-build -w tmp/sphinx.out -b html documentation html

doc-img:
	plantuml sphinx/driver_api.txt
	plantuml sphinx/proxy_api.txt

upload-doc:
	rsync -avzP -e ssh html/ mathias_laurin@web.sourceforge.net:/home/project-web/pyhard2/htdocs/ 

export:
	git archive $(CUR_BRANCH) --format=zip > /Users/laurin/Desktop/pyhard2-code.zip

rcc:
	pyrcc4 -o pyhard2/rsc/__init__.py pyhard2/rsc/resources.qrc

lint:
	pylint --disable=C0103 pyhard2

sloccount:
	sloccount --duplicates --wide --details .

virtual-conf:
	gsed -r 's/^( *driver:).*$$/\1 virtual/g' circat.yml > virtual-circat.yml

