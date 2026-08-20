# Which Python interpreter to use - the ONE HOME for that selection (#859).
#
# Sourced, not executed: .claude/hooks/session-start.sh installs into the
# interpreter pick_python names, and scripts/test.sh / scripts/threads.sh run
# with an interpreter python_with proves can do the job. #859 is what happens
# when the two halves decide differently: the hook went to real trouble to
# install into 3.13, test.sh shelled out to bare `python` - Debian's 3.11,
# first on PATH - and the one command CLAUDE.md names died on its first step
# with "No module named ruff", a message that reads as a missing package when
# the truth is a wrong interpreter.
#
# Callers source this from the repository root, which is where both callers
# already are: ci_python_version reads a workflow by relative path.
#
# WHY CHOSEN RATHER THAN HARDCODED (#822, the install-side half of this).
# Both obvious constants are wrong within one image update: naming
# `python3.13` breaks when the image ships 3.14 or drops 3.13, and naming
# CI's version breaks whenever the image does not have it. So: prefer the
# version CI actually uses, read out of the workflow rather than copied (one
# home for it), and otherwise take the newest interpreter present. Newest,
# not `python3` - the original failure was that `python3` is the OLDEST
# thing installed.
#
# There is no floor test here on purpose. If the chosen interpreter cannot
# satisfy the pins, pip says so by name and the hook's gate fails loudly -
# which is better than a floor that has to be kept in step with whatever the
# lockfiles currently need.

ci_python_version() {
  sed -n 's/^[[:space:]]*python-version:[[:space:]]*"\([0-9][0-9.]*\)".*/\1/p' \
    .github/workflows/pipeline-tests.yml | head -1
}

available_pythons() {
  # Real interpreters only - `ls python3.*` also matches python3.11-config.
  ls -1 /usr/local/bin/python3.* /usr/bin/python3.* 2>/dev/null \
    | grep -E '/python3\.[0-9]+$' \
    | xargs -r -n1 basename \
    | sort -u -t. -k2 -n -r
}

pick_python() {
  local ci
  ci="$(ci_python_version)"
  local candidate
  for candidate in ${ci:+"python${ci}"} $(available_pythons); do
    if command -v "${candidate}" >/dev/null 2>&1; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

# The first interpreter that can import every module named, or failure.
#
# This is the RUNNER's side of the selection, and it asks a different
# question from pick_python's. The hook decides where to install, so it wants
# "the interpreter CI uses"; a runner wants "the interpreter the tools are
# actually installed under", which is a fact to probe rather than infer. Bare
# `python` and `python3` are tried first - a developer's activated venv is
# exactly the interpreter they installed into, and it must win over anything
# this repository would pick for them - and pick_python's choice last, which
# on a web session is the interpreter the session-start hook provisioned.
python_with() {
  local candidate
  for candidate in python python3 "$(pick_python 2>/dev/null || true)"; do
    [ -n "${candidate}" ] || continue
    command -v "${candidate}" >/dev/null 2>&1 || continue
    "${candidate}" -c "import $(IFS=,; echo "$*")" >/dev/null 2>&1 || continue
    echo "${candidate}"
    return 0
  done
  return 1
}
