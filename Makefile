# Print the version recorded in urlscan/__init__.py
version:
	@grep -Po '^__version__ = "\K[^"]+' urlscan/__init__.py

# Run the test suite. Uses pytest straight off PATH when it is there, as it is
# inside `nix develop`; otherwise enters the dev shell to get it.
# Usage: make test [PYTEST_ARGS="-k context -v"]
test:
	@if command -v pytest >/dev/null 2>&1; then \
		pytest $(PYTEST_ARGS); \
	else \
		nix develop --command pytest $(PYTEST_ARGS); \
	fi

# Bump __version__, refresh the man page date, commit, and create an annotated
# tag. $EDITOR prefilled with version and commits since the last tag.
# Usage: make release VERSION=1.1.0
release:
	@test -n "$(VERSION)" || { echo "Usage: make release VERSION=x.y.z"; exit 1; }
	@echo "$(VERSION)" | grep -Pq '^\d+\.\d+\.\d+$$' || \
		{ echo "VERSION must be x.y.z"; exit 1; }
	@test -z "$$(git status --porcelain -uno)" || \
		{ echo "Tracked files have uncommitted changes; commit or stash first"; exit 1; }
	@git rev-parse -q --verify refs/tags/$(VERSION) >/dev/null && \
		{ echo "Tag $(VERSION) already exists"; exit 1; } || true
	sed -i 's/^__version__ = ".*"$$/__version__ = "$(VERSION)"/' urlscan/__init__.py
	# urlscan.1 is hand-written roff, so only the .TH date is refreshed here.
	sed -i "s/^\.TH URLSCAN 1 \".*\"/.TH URLSCAN 1 \"$$(date '+%-d %B %Y')\"/" \
		urlscan.1
	@test "$$($(MAKE) -s version)" = "$(VERSION)" || \
		{ echo "Failed to set version"; exit 1; }
	git commit -m "Bump version to $(VERSION)" urlscan/__init__.py urlscan.1
	# Open the tag message prefilled with the version as the subject and one
	# bullet per commit since the last tag.
	@notes=$$(mktemp); \
	prev=$$(git describe --tags --abbrev=0 2>/dev/null); \
	{ echo "$(VERSION)"; echo; \
	  git log --no-merges --invert-grep \
		--grep='^Bump version to ' --format='* %s' \
		$${prev:+$$prev..}HEAD; } > $$notes; \
	git tag -a -e -F $$notes $(VERSION); status=$$?; \
	rm -f $$notes; \
	test $$status -eq 0 || exit $$status; \
	test -n "$$(git for-each-ref --format='%(contents:body)' \
		refs/tags/$(VERSION))" || { \
		git tag -d $(VERSION) >/dev/null; \
		echo "Tag message body is empty, so the release notes would be too."; \
		echo "Tag not created. The version bump commit is still there;"; \
		echo "undo it with: git reset --hard HEAD^"; \
		exit 1; }
	@echo
	@echo "Tagged $(VERSION). Push with:"
	@echo "    git push origin $$(git rev-parse --abbrev-ref HEAD) --follow-tags"

.PHONY: version release test
