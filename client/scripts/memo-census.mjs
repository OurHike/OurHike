// Which of App.tsx's memoised values anything actually depends on (#1454).
//
// WHY THIS EXISTS. client/README.md's "What the memoisation policy is" carried
// `@unvalidated` and named exactly this as what would settle it: "Each
// useCallback/useMemo in App.tsx either appears in some dependency array or it
// does not, and that is a mechanical question a script can answer. Nobody has
// run it." This is the script, committed rather than run once and quoted, so
// the number moves when the file does.
//
// WHAT THE ANSWER MEANS, and the two halves must not be added together:
//
//   - A `useCallback` in NO dependency array is very likely cargo IN THIS
//     CODEBASE, and the qualifier is load-bearing. A stable callback identity
//     pays off against a memoised child or against another hook's dependency
//     array. This client has zero `React.memo` and no React Compiler, so the
//     first payoff does not exist here at all. Take both away and what is left
//     is a function wrapped for nothing.
//   - A `useMemo` in NO dependency array MAY STILL BE LOAD-BEARING, and
//     calling it cargo would be wrong. `useMemo` also buys not recomputing
//     something expensive, which has nothing to do with identity. So the
//     number below says "not load-bearing FOR IDENTITY" and stops; whether the
//     computation earns its keep is a per-site question no script answers.
//
// TRANSITIVITY WITHIN THE FILE NEEDS NO HANDLING, which is worth saying
// because it looks like it might. If `x` is referenced inside hook `y`'s body,
// exhaustive-deps puts `x` in `y`'s dependency array, so `x` is already
// counted. A value used only inside another hook is not a hidden case.
//
// TRANSITIVITY ACROSS THE PROP BOUNDARY DOES, and missing it is what would
// have made this census a confidently wrong number. A callback in no
// dependency array in App.tsx can still be held stable for a CHILD's effect:
// `MapView` keys eight of its 48 effects on callbacks the shell passes it, and
// says so at the prop - "stable across renders (useCallback), like
// `onSelectPoi`" (map/MapView.tsx:302). An unstable identity there re-runs
// that effect on every render of the shell, which is precisely what the
// `useCallback` is buying. Counting only App.tsx's own arrays would have
// called 126 of them cargo, and a large share of those are load-bearing one
// file away.
//
// So the census follows each value to the prop names it is passed as - through
// JSX attributes and through the object literals the panel hooks return - and
// asks whether THAT name appears in a dependency array anywhere under src/.
// Where a prop name is ambiguous the answer errs toward "load-bearing", which
// is the direction that cannot manufacture a deletion.
//
// WHY A REAL PARSER. App.tsx holds 184 single-line dependency arrays and 90
// that span lines, plus declarations that destructure (`const { closureAhead,
// advisoryAhead } = useMemo(...)`). A regex over that is a guess wearing a
// number's clothes.
//
// `typescript` is NOT the parser here, which is worth recording because it is
// the obvious choice and it does not work: the pinned `typescript` is 7.0.2,
// the Go rewrite, and it ships no `createSourceFile` - `ts.version` resolves
// and every compiler-API call is `undefined`. `@babel/parser` is what the
// client already builds through (`@vitejs/plugin-react` -> `@babel/core`) and
// it parses this file as TSX without configuration.
//
// AND A GUARD ON THE PARSE ITSELF, because a parser that quietly reads part of
// a file produces a confident wrong number, which is the failure this whole
// census exists to replace. `--check` re-counts the declarations by text and
// fails if the AST disagrees. `src/test/memoCensus.test.ts` runs the real
// script against synthetic fixtures and asserts it goes red on a bad parse.
//
// `@babel/parser` is a TRANSITIVE dependency here, not a declared one, and
// that is a deliberate trade rather than an oversight: declaring it to run a
// measurement script would churn package-lock.json, which is one of the files
// BRANCHING.md measures as a conflict surface. The cost is that a future
// dependency bump could take it away - so the require below fails loudly and
// says what to do, which is a visible error rather than a wrong number.
//
// Usage: node scripts/memo-census.mjs [path]   (default: src/App.tsx)
//        node scripts/memo-census.mjs --json   the raw counts
//        node scripts/memo-census.mjs --check  verify the parse against the text

import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'

const require = createRequire(import.meta.url)

let parse
try {
  ;({ parse } = require('@babel/parser'))
} catch {
  console.error(
    '@babel/parser is not resolvable. It reaches this script through\n' +
      '@vitejs/plugin-react -> @babel/core, so a dependency change has removed\n' +
      'it. Either add it to devDependencies or point this script at another\n' +
      'TSX parser - `typescript` is NOT one, see the header.',
  )
  process.exit(1)
}

/** The hooks whose second argument is a dependency array. */
const HOOKS_WITH_DEPS = new Set([
  'useCallback',
  'useMemo',
  'useEffect',
  'useLayoutEffect',
  'useImperativeHandle',
])

/** The hooks this census is about. */
const MEMO_HOOKS = ['useCallback', 'useMemo']

/**
 * Every name a declaration binds, so a destructured memo counts each field.
 *
 * `const { a, b } = useMemo(...)` is one memo and two names, and either name
 * appearing in a dependency array makes the memo load-bearing.
 */
function boundNames(node, into = []) {
  if (node === null || node === undefined) return into
  switch (node.type) {
    case 'Identifier':
      into.push(node.name)
      break
    case 'ObjectPattern':
      for (const property of node.properties) {
        boundNames(
          property.type === 'RestElement' ? property.argument : property.value,
          into,
        )
      }
      break
    case 'ArrayPattern':
      for (const element of node.elements) boundNames(element, into)
      break
    case 'AssignmentPattern':
      boundNames(node.left, into)
      break
    case 'RestElement':
      boundNames(node.argument, into)
      break
    default:
      break
  }
  return into
}

/** The hook name for a call node, covering `useMemo()` and `React.useMemo()`. */
function hookName(node) {
  if (node.type !== 'CallExpression') return null
  const callee = node.callee
  if (callee.type === 'Identifier') return callee.name
  if (callee.type === 'MemberExpression' && callee.property.type === 'Identifier') {
    return callee.property.name
  }
  return null
}

/** Walk every node, without pulling in @babel/traverse. */
function walk(node, visit) {
  if (node === null || typeof node !== 'object') return
  if (Array.isArray(node)) {
    for (const child of node) walk(child, visit)
    return
  }
  if (typeof node.type === 'string') visit(node)
  for (const key of Object.keys(node)) {
    if (key === 'loc' || key === 'leadingComments' || key === 'trailingComments') continue
    walk(node[key], visit)
  }
}

/** Parse one file, tolerating nothing quietly. */
function astOf(filePath) {
  return parse(readFileSync(filePath, 'utf8'), {
    sourceType: 'module',
    plugins: ['typescript', 'jsx'],
  })
}

/** Every identifier inside any dependency array in one file. */
function dependedIn(ast) {
  const found = new Set()
  walk(ast.program, (node) => {
    const hook = hookName(node)
    if (hook === null || !HOOKS_WITH_DEPS.has(hook)) return
    const deps = node.arguments[1]
    if (deps === undefined || deps.type !== 'ArrayExpression') return
    walk(deps.elements, (inner) => {
      if (inner.type === 'Identifier') found.add(inner.name)
    })
  })
  return found
}

export function census(filePath, sourceRoot) {
  const source = readFileSync(filePath, 'utf8')
  const ast = astOf(filePath)

  /** One entry per memoised value. */
  const memos = []
  /** Every identifier appearing inside any dependency array. */
  const depended = new Set()

  walk(ast.program, (node) => {
    const hook = hookName(node)
    if (hook === null) return

    if (HOOKS_WITH_DEPS.has(hook)) {
      const deps = node.arguments[1]
      if (deps !== undefined && deps.type === 'ArrayExpression') {
        // `a.b` and `a?.[b]` depend on `a`; take the root of each element.
        walk(deps.elements, (inner) => {
          if (inner.type === 'Identifier') depended.add(inner.name)
        })
      }
    }

    if (!MEMO_HOOKS.includes(hook)) return
    memos.push({ hook, call: node, line: node.loc?.start.line ?? 0 })
  })

  // Attach the declaration each memo is assigned to, which is what names it.
  walk(ast.program, (node) => {
    if (node.type !== 'VariableDeclarator' || node.init === null) return
    const memo = memos.find((entry) => entry.call === node.init)
    if (memo === undefined) return
    memo.names = boundNames(node.id)
  })

  // The prop names each value is handed on as: `onSelectPoi={handleSelectPoi}`
  // in JSX, and `{ onSelectPoi: handleSelectPoi }` or `{ onSelectPoi }` in the
  // object literals the panel hooks return.
  const aliasesOf = new Map()
  const alias = (from, to) => {
    if (!aliasesOf.has(from)) aliasesOf.set(from, new Set())
    aliasesOf.get(from).add(to)
  }
  // A THIRD BOUNDARY, found by hand-checking the first run's output rather
  // than by reasoning: a value handed to a CUSTOM hook.
  // `useOutboxSync(online && account !== null, handleSynced)` puts
  // `handleSynced` in no array and on no JSX prop, and lib/outboxSync.ts:115
  // says of it "must be referentially stable, or this re-runs on every
  // render". Counting it cargo would have been flatly wrong.
  //
  // This is an OVER-APPROXIMATION and deliberately so: it assumes any custom
  // hook may key an effect on the arguments it is given, without opening that
  // hook to check. Resolving each import to confirm would be more exact and
  // could only move values INTO the cargo bucket, which is the direction that
  // manufactures deletions. Erring the other way costs an honest overcount.
  const handedToHook = new Set()
  walk(ast.program, (node) => {
    if (node.type !== 'CallExpression' || node.callee.type !== 'Identifier') return
    const name = node.callee.name
    if (!/^use[A-Z]/.test(name) || HOOKS_WITH_DEPS.has(name) || name === 'useState')
      return
    for (const argument of node.arguments) {
      walk(argument, (inner) => {
        if (inner.type === 'Identifier') handedToHook.add(inner.name)
      })
    }
  })

  walk(ast.program, (node) => {
    if (
      node.type === 'JSXAttribute' &&
      node.name?.type === 'JSXIdentifier' &&
      node.value?.type === 'JSXExpressionContainer' &&
      node.value.expression.type === 'Identifier'
    ) {
      alias(node.value.expression.name, node.name.name)
      return
    }
    if (node.type === 'ObjectProperty' && node.key?.type === 'Identifier') {
      if (node.value?.type === 'Identifier') alias(node.value.name, node.key.name)
    }
  })

  // Every identifier in a dependency array ANYWHERE under src/, which is what
  // makes the prop-boundary case visible. Tests are excluded: a dependency
  // array in a test file is the test's own, not the shell's contract.
  const everywhere = new Set(depended)
  if (sourceRoot !== undefined) {
    for (const file of tsFilesUnder(sourceRoot)) {
      if (file === filePath) continue
      for (const name of dependedIn(astOf(file))) everywhere.add(name)
    }
  }

  for (const memo of memos) {
    memo.names ??= []
    // A memo nothing binds - passed straight into a call - can be depended on
    // by nothing, so it lands in the same bucket as an unused name.
    memo.local = memo.names.some((name) => depended.has(name))
    memo.passedAs = [
      ...new Set(memo.names.flatMap((name) => [...(aliasesOf.get(name) ?? [])])),
    ]
    memo.acrossBoundary =
      !memo.local && memo.passedAs.some((prop) => everywhere.has(prop))
    memo.handedToHook =
      !memo.local &&
      !memo.acrossBoundary &&
      memo.names.some((name) => handedToHook.has(name))
    memo.depended = memo.local || memo.acrossBoundary || memo.handedToHook
    delete memo.call
  }

  return { memos, depended, everywhere, source }
}

/** Every non-test .ts/.tsx under a directory. */
function tsFilesUnder(root) {
  const out = []
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name)
    if (entry.isDirectory()) {
      out.push(...tsFilesUnder(path))
      continue
    }
    if (!/\.tsx?$/.test(entry.name)) continue
    if (/\.(test|spec)\./.test(entry.name)) continue
    out.push(path)
  }
  return out
}

function summarise(memos) {
  const rows = {}
  for (const hook of MEMO_HOOKS) {
    const mine = memos.filter((memo) => memo.hook === hook)
    rows[hook] = {
      total: mine.length,
      local: mine.filter((memo) => memo.local).length,
      acrossBoundary: mine.filter((memo) => memo.acrossBoundary).length,
      handedToHook: mine.filter((memo) => memo.handedToHook).length,
      depended: mine.filter((memo) => memo.depended).length,
      orphaned: mine.filter((memo) => !memo.depended).length,
    }
  }
  return rows
}

/**
 * Does the AST agree with the text about how many hooks are in this file?
 *
 * Counts `useCallback(` / `useMemo(` occurrences outside comments and strings.
 * A mismatch means the parse is reading something other than the whole file,
 * and every number above it is void.
 */
export function checkParse(filePath, memos) {
  const source = readFileSync(filePath, 'utf8')
  const stripped = source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')
    .replace(/'(?:\\.|[^'\\])*'/g, "''")
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/`(?:\\.|[^`\\])*`/g, '``')

  const problems = []
  for (const hook of MEMO_HOOKS) {
    const inText = (stripped.match(new RegExp(`\\b${hook}\\s*[(<]`, 'g')) ?? []).length
    const inAst = memos.filter((memo) => memo.hook === hook).length
    if (inText !== inAst) {
      problems.push(`${hook}: text says ${inText}, AST says ${inAst}`)
    }
  }
  return problems
}

const target = process.argv.find((argument) => argument.endsWith('.tsx'))
const path = resolve(target ?? 'src/App.tsx')
const { memos } = census(path, resolve(dirname(path)))
const rows = summarise(memos)

if (process.argv.includes('--check')) {
  const problems = checkParse(path, memos)
  if (problems.length > 0) {
    console.error('the parse disagrees with the text, so the census is void:')
    for (const problem of problems) console.error(`  ${problem}`)
    process.exit(1)
  }
  console.log('parse agrees with the text')
  process.exit(0)
}

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ path, rows, memos }, null, 2))
} else {
  console.log(`\n${path}\n`)
  for (const hook of MEMO_HOOKS) {
    const row = rows[hook]
    const share = row.total === 0 ? '0.0' : ((row.depended / row.total) * 100).toFixed(1)
    console.log(
      `  ${hook.padEnd(12)} ${String(row.total).padStart(4)} total   ` +
        `${String(row.local).padStart(4)} in an array here   ` +
        `${String(row.acrossBoundary).padStart(4)} via a prop a child depends on   ` +
        `${String(row.handedToHook).padStart(4)} handed to a custom hook   ` +
        `${String(row.orphaned).padStart(4)} none of those   (${share}% depended on)`,
    )
  }
  console.log('\n  The last column is the candidate set, not a delete list: for a')
  console.log('  useCallback it is very likely cargo here (zero React.memo, no')
  console.log('  React Compiler), and for a useMemo it may still be earning its')
  console.log('  keep by not recomputing - which is a per-site question.\n')
  console.log('  useCallbacks depended on by nobody:')
  for (const memo of memos) {
    if (memo.hook !== 'useCallback' || memo.depended) continue
    const as = memo.passedAs.length > 0 ? `  (passed as ${memo.passedAs.join(', ')})` : ''
    console.log(
      `    App.tsx:${String(memo.line).padEnd(6)} ${memo.names.join(', ') || '(unbound)'}${as}`,
    )
  }
  console.log('')
}
