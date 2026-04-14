.ONESHELL:
.SHELLFLAGS = -ec

version := $(shell python -c "import sys; sys.path.insert(0, '.'); from unapicker import __version__; print(__version__)")

.PHONY: dist
dist:
	python -m build

.PHONY: release
release: dist
	# check that changelog is updated
	version=$(version)
	stripped=$$(echo $${version} | cut -d . -f -3 | cut -d '-' -f 1)
	if ! grep -q $${stripped} CHANGELOG.md 2>/dev/null
	then
		echo "Warning: Changelog doesn't seem to be updated for version $${stripped}"
	fi
	gh release create --latest --verify-tag v$(version) dist/unapicker-$(version)* || true
	twine upload dist/unapicker-$(version).tar.gz

.PHONY: release_nonotes
release_nonotes: dist
	gh release create --latest --verify-tag v$(version) dist/unapicker-$(version)*
	twine upload dist/unapicker-$(version).tar.gz

.PHONY: install_dev
install_dev:
	pip install -e ".[dev]"
	pip install build twine

.PHONY: clean
clean:
	rm -rf build dist *.egg-info
