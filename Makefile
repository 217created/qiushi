.PHONY: install chat

install:
	pip install -e .

chat:
	qiushi chat

teach:
	qiushi chat --mode teach
