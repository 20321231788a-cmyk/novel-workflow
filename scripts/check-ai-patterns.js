#!/usr/bin/env node
'use strict';

// Read-only expression diagnostics. Rules are data, not an authorship verdict.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const REPORT_SCHEMA = 'story-deslop.expression-scan.v1';
const USAGE = `Usage: node check-ai-patterns.js [--check] [--json]
  [--library-dir PATH] [--profile PATH] [--output REPORT.json]
  [--fail-on=none|blocking|all] <file...>

Read versioned wording, syntax and semantic policy diagnostics from JSON files.
Default --fail-on=none: all findings require contextual human review.
prohibit_after_verification rules produce candidate_policy findings only.
Rules without detectors appear in manual_checks; they are not declared passed.
All prohibit_after_verification rules also appear in semantic_checks and require
full-text human source review. Detector coverage is partial; no hit is not a pass.
--fail-on=blocking is compatible but does not promote any diagnostic rule.
--fail-on=all explicitly returns 1 if a diagnostic finding is present.
Input files, libraries and profiles are never rewritten. Only --output writes a
JSON report. It cannot overwrite inputs, rules, profiles or another artifact.
Exit codes: 0 completed; 1 explicitly requested findings exit; 2 input/rule error.`;

function main(argv) {
  const options = parseOptions(argv);
  if (options.help) { process.stdout.write(`${USAGE}\n`); return 0; }
  const library = loadLibrary(options.libraryDir, options.profile);
  const inputPaths = [...new Set(options.files.map((file) => path.resolve(file)))];
  if (options.output) validateOutput(options.output, inputPaths, library);
  const report = { schema: REPORT_SCHEMA, library_version: library.version,
    library_files: library.sources, profile: library.profile, read_only: true,
    fail_on: options.failOn,
    interpretation: 'Diagnostic candidates only; no AI authorship verdict, score or automatic delivery gate.',
    inputs: [], findings: [],
    manual_checks: library.rules.filter((rule) => rule.detectors.length === 0).map(manualCheck),
    semantic_checks: library.rules.filter((rule) => rule.enforcement === 'prohibit_after_verification').map(semanticCheck) };
  for (const file of inputPaths) {
    const bytes = fs.readFileSync(file);
    const input = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
    const paragraphs = parseProse(input);
    const findings = scanDocument(input, paragraphs, library.rules).map((finding) => ({ file, ...finding }));
    report.inputs.push({ file, sha256: sha256(bytes), findings_count: findings.length,
      chapter_titles: [...new Set(paragraphs.map((paragraph) => paragraph.chapter).filter(Boolean))] });
    report.findings.push(...findings);
  }
  const serialized = `${JSON.stringify(report, null, 2)}\n`;
  if (options.output) fs.writeFileSync(path.resolve(options.output), serialized, 'utf8');
  if (options.json) process.stdout.write(serialized);
  else printText(report, options.output);
  return options.failOn === 'all' && report.findings.length ? 1 : 0;
}

function parseOptions(argv) {
  const options = { json: false, files: [], failOn: 'none',
    libraryDir: path.resolve(__dirname, '../references/表达规范库'), profile: null, output: null, help: false };
  const values = { '--library-dir': 'libraryDir', '--profile': 'profile', '--output': 'output' };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--check') continue;
    if (arg === '--json') options.json = true;
    else if (arg === '-h' || arg === '--help') options.help = true;
    else if (arg.startsWith('--fail-on=')) options.failOn = arg.slice('--fail-on='.length);
    else if (arg === '--fail-on') {
      if (!argv[index + 1] || argv[index + 1].startsWith('--')) throw new Error('--fail-on requires a value');
      options.failOn = argv[++index];
    } else if (Object.hasOwn(values, arg)) {
      if (!argv[index + 1] || argv[index + 1].startsWith('--')) throw new Error(`${arg} requires a path`);
      options[values[arg]] = argv[++index];
    } else if (Object.keys(values).some((flag) => arg.startsWith(`${flag}=`))) {
      const separator = arg.indexOf('=');
      const value = arg.slice(separator + 1);
      if (!value) throw new Error(`${arg.slice(0, separator)} requires a path`);
      options[values[arg.slice(0, separator)]] = value;
    } else if (arg.startsWith('-')) throw new Error(`Unknown option: ${arg}`);
    else options.files.push(arg);
  }
  if (!['none', 'blocking', 'all'].includes(options.failOn)) throw new Error('--fail-on must be none, blocking or all');
  if (!options.help && options.files.length === 0) throw new Error('No files provided');
  return options;
}

function sha256(bytes) { return crypto.createHash('sha256').update(bytes).digest('hex'); }
function nonempty(value) { return typeof value === 'string' && value.trim().length > 0; }
function positiveInteger(value) { return Number.isInteger(value) && value > 0; }

function readJson(file) {
  const bytes = fs.readFileSync(file);
  let value;
  try { value = JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/u, '')); }
  catch (error) { throw new Error(`Invalid JSON in ${file}: ${error.message}`); }
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error(`Expected JSON object: ${file}`);
  return { value, source: { path: path.resolve(file), sha256: sha256(bytes) } };
}

function loadLibrary(directory, profilePath) {
  const root = path.resolve(directory);
  const manifestPath = path.join(root, 'manifest.json');
  const manifest = readJson(manifestPath);
  const value = manifest.value;
  if (value.schema_version !== 1 || !nonempty(value.library_version)
      || !Array.isArray(value.files) || value.files.length === 0) throw new Error(`Invalid rule manifest: ${manifestPath}`);
  if (new Set(value.files).size !== value.files.length) throw new Error('Duplicate rule files in manifest');
  const rules = [];
  const sources = [manifest.source];
  for (const name of value.files) {
    if (!nonempty(name) || path.basename(name) !== name || !name.endsWith('.json')
        || name === 'manifest.json') throw new Error('Manifest files must be JSON filenames within the library');
    const file = path.join(root, name);
    if (!within(canonical(root), canonical(file))) throw new Error(`Rule file is outside the library: ${file}`);
    const loaded = readJson(file);
    if (loaded.value.library_version !== value.library_version) throw new Error(`Rule version mismatch: ${file}`);
    rules.push(...validateRules(loaded.value, file));
    sources.push(loaded.source);
  }
  let profile = null;
  if (profilePath) {
    const loaded = readJson(path.resolve(profilePath));
    rules.push(...validateRules(loaded.value, loaded.source.path));
    profile = { ...loaded.source, library_version: loaded.value.library_version, kind: loaded.value.kind };
  }
  const ids = new Set();
  for (const rule of rules) {
    if (ids.has(rule.id)) throw new Error(`Duplicate rule ID: ${rule.id}`);
    ids.add(rule.id);
  }
  return { root, version: value.library_version, rules, sources, profile };
}

function validateRules(document, file) {
  if (document.schema_version !== 1 || !nonempty(document.library_version)
      || !nonempty(document.kind) || !Array.isArray(document.rules)) throw new Error(`Invalid rule collection: ${file}`);
  return document.rules.map((raw) => {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error(`Invalid rule in ${file}`);
    for (const key of ['id', 'name', 'scope', 'diagnosis', 'revision']) {
      if (!nonempty(raw[key])) throw new Error(`Missing ${key} for rule ${raw.id || '(unknown)'} in ${file}`);
    }
    if (!['review', 'prohibit_after_verification'].includes(raw.enforcement)) throw new Error(`Invalid enforcement: ${raw.id}`);
    if (raw.manual_review_required !== true) throw new Error(`Rule must require manual review: ${raw.id}`);
    for (const key of ['retain_when', 'evidence_ids']) {
      if (!Array.isArray(raw[key]) || !raw[key].every(nonempty)) throw new Error(`Invalid ${key}: ${raw.id}`);
    }
    if (raw.detectors !== undefined && !Array.isArray(raw.detectors)) throw new Error(`Invalid detectors: ${raw.id}`);
    const detectors = (raw.detectors || []).map((detector) => validateDetector(detector, raw.id));
    return { ...raw, detectors, source: path.resolve(file), kind: document.kind };
  });
}

function validateDetector(raw, id) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)
      || !['regex', 'cooccurrence'].includes(raw.type)) throw new Error(`Invalid detector type: ${id}`);
  if (!['paragraph', 'prose_window'].includes(raw.window)) throw new Error(`Invalid detector window: ${id}`);
  const windowSize = raw.window_size === undefined ? 4 : raw.window_size;
  if (!positiveInteger(windowSize) || windowSize > 100) throw new Error(`Invalid window_size: ${id}`);
  if (raw.type === 'regex') {
    if (!nonempty(raw.pattern)) throw new Error(`Missing regex pattern: ${id}`);
    const minimum = raw.min_matches === undefined ? 1 : raw.min_matches;
    if (!positiveInteger(minimum)) throw new Error(`Invalid min_matches: ${id}`);
    let regex;
    try { regex = new RegExp(raw.pattern, 'gu'); }
    catch (error) { throw new Error(`Invalid regex for ${id}: ${error.message}`); }
    return { ...raw, window_size: windowSize, min_matches: minimum, regex };
  }
  if (!Array.isArray(raw.terms) || raw.terms.length === 0 || !raw.terms.every(nonempty)
      || new Set(raw.terms).size !== raw.terms.length) throw new Error(`Invalid cooccurrence terms: ${id}`);
  if (!positiveInteger(raw.min_distinct) || raw.min_distinct > raw.terms.length) throw new Error(`Invalid min_distinct: ${id}`);
  return { ...raw, window_size: windowSize };
}

// Blank lines and 2+ full-width spaces at the start of a line begin paragraphs.
// Unindented wrapped lines stay together; excluded structures reset windows.
function parseProse(input) {
  const lines = physicalLines(input);
  const tableLines = markdownTableLines(lines);
  const paragraphs = [];
  let block = [];
  let chapter = null;
  let section = 0;
  let fence = null;
  let frontMatter = hasFrontMatter(lines);
  const flush = () => {
    if (block.length) {
      paragraphs.push({ start: block[0].start, end: block[block.length - 1].end, chapter, section });
      block = [];
    }
  };
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.text.replace(/^\uFEFF/u, '').trim();
    if (frontMatter) {
      if (index > 0 && trimmed === '---') frontMatter = false;
      continue;
    }
    const marker = /^(?<chars>`{3,}|~{3,})/u.exec(trimmed);
    if (fence) {
      if (marker && marker.groups.chars[0] === fence[0] && marker.groups.chars.length >= fence.length) fence = null;
      continue;
    }
    if (marker) { flush(); section += 1; fence = marker.groups.chars; continue; }
    const heading = /^#{1,6}\s+(.+)$/u.exec(trimmed);
    const title = heading ? heading[1].trim() : trimmed;
    const isChapter = /^第[零〇一二三四五六七八九十百千万两0-9０-９]+[章回卷节]/u.test(title)
      || /^chapter\s+\d+\b/iu.test(title);
    if (heading || isChapter) {
      flush(); section += 1;
      if (isChapter) chapter = title;
      continue;
    }
    if (tableLines.has(index) || /^\|/u.test(trimmed) || /^(?:[-*_]){3,}$/u.test(trimmed)) {
      flush(); section += 1; continue;
    }
    if (!trimmed) flush();
    else {
      if (/^\u3000{2,}/u.test(line.text.replace(/^\uFEFF/u, ''))) flush();
      block.push(line);
    }
  }
  flush();
  return paragraphs;
}

function physicalLines(input) {
  const lines = [];
  const matcher = /([^\r\n]*)(\r\n|\r|\n|$)/gu;
  let match;
  while ((match = matcher.exec(input)) !== null) {
    lines.push({ text: match[1], start: match.index, end: match.index + match[1].length });
    if (match[2] === '') break;
  }
  return lines;
}

function hasFrontMatter(lines) {
  if (!lines.length || lines[0].text.replace(/^\uFEFF/u, '').trim() !== '---') return false;
  let field = false;
  for (let index = 1; index < Math.min(lines.length, 100); index += 1) {
    const trimmed = lines[index].text.trim();
    if (trimmed === '---') return field;
    if (/^[^:#\s][^:]*:\s*/u.test(trimmed)) field = true;
  }
  return false;
}

function markdownTableLines(lines) {
  const tableLines = new Set();
  for (let index = 1; index < lines.length; index += 1) {
    const separator = lines[index].text.trim();
    if (!separator.includes('|')) continue;
    const cells = separator.replace(/^\|/u, '').replace(/\|$/u, '').split('|').map((cell) => cell.trim());
    if (!cells.length || !cells.every((cell) => /^:?-{3,}:?$/u.test(cell))
        || !lines[index - 1].text.includes('|')) continue;
    tableLines.add(index - 1);
    tableLines.add(index);
    for (let next = index + 1; next < lines.length && lines[next].text.includes('|'); next += 1) tableLines.add(next);
  }
  return tableLines;
}

function windows(paragraphs, detector) {
  if (detector.window === 'paragraph') return paragraphs;
  return paragraphs.map((first, index) => {
    let last = first;
    for (let next = index + 1; next < Math.min(paragraphs.length, index + detector.window_size); next += 1) {
      if (paragraphs[next].section !== first.section) break;
      last = paragraphs[next];
    }
    return { start: first.start, end: last.end, chapter: first.chapter, section: first.section };
  });
}

function scanDocument(input, paragraphs, rules) {
  const findings = [];
  const seen = new Set();
  const lineStarts = physicalLines(input).map((line) => line.start);
  for (const rule of rules) {
    for (const detector of rule.detectors) {
      for (const window of windows(paragraphs, detector)) {
        const text = input.slice(window.start, window.end);
        for (const match of detectorMatches(text, detector)) {
          const start = window.start + match.start;
          const end = window.start + match.end;
          const key = `${rule.id}:${start}:${end}`;
          if (seen.has(key)) continue;
          seen.add(key);
          const position = positionForOffset(input, lineStarts, start);
          const endPosition = positionForOffset(input, lineStarts, end);
          findings.push({ rule_id: rule.id, rule_name: rule.name, kind: rule.kind,
            severity: rule.enforcement === 'prohibit_after_verification' ? 'candidate_policy' : 'review',
            enforcement: rule.enforcement, scope: rule.scope, chapter_title: window.chapter,
            line: position.line, column: position.column, end_line: endPosition.line, end_column: endPosition.column,
            offset_start: start, offset_end: end, matched: input.slice(start, end),
            detector_type: detector.type, matched_terms: match.terms || null,
            reason: rule.diagnosis, revision: rule.revision, retain_when: rule.retain_when,
            evidence_ids: rule.evidence_ids, rule_source: rule.source,
            manual_review_required: true, needs_human_review: true });
        }
      }
    }
  }
  return findings.sort((left, right) => left.offset_start - right.offset_start || left.rule_id.localeCompare(right.rule_id));
}

function detectorMatches(text, detector) {
  if (detector.type === 'regex') {
    const matches = [];
    detector.regex.lastIndex = 0;
    let match;
    while ((match = detector.regex.exec(text)) !== null) {
      if (match[0].length === 0) {
        detector.regex.lastIndex += (text.codePointAt(detector.regex.lastIndex) > 0xFFFF ? 2 : 1);
        continue;
      }
      matches.push({ start: match.index, end: match.index + match[0].length });
    }
    return matches.length >= detector.min_matches ? matches : [];
  }
  const terms = detector.terms.map((term) => ({ term, index: text.indexOf(term) })).filter((item) => item.index !== -1);
  if (terms.length < detector.min_distinct) return [];
  return [{ start: Math.min(...terms.map((item) => item.index)),
    end: Math.max(...terms.map((item) => item.index + item.term.length)), terms: terms.map((item) => item.term) }];
}

function positionForOffset(input, lineStarts, offset) {
  let low = 0;
  let high = lineStarts.length - 1;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (lineStarts[mid] > offset) high = mid - 1;
    else low = mid + 1;
  }
  const index = Math.max(0, high);
  return { line: index + 1, column: Array.from(input.slice(lineStarts[index] || 0, offset)).length + 1 };
}

function manualCheck(rule) {
  return { rule_id: rule.id, rule_name: rule.name, kind: rule.kind, scope: rule.scope,
    enforcement: rule.enforcement, reason: rule.diagnosis, revision: rule.revision,
    retain_when: rule.retain_when, evidence_ids: rule.evidence_ids, rule_source: rule.source,
    status: 'not_automatically_checked', manual_review_required: true, needs_human_review: true };
}

function semanticCheck(rule) {
  return { ...manualCheck(rule), status: 'requires_full_text_human_review',
    detector_count: rule.detectors.length, detector_coverage_partial: true,
    human_review_requirement: '必须通读全文并核对来源；检测器仅覆盖部分线索，未命中不代表通过。' };
}

function canonical(file) {
  const resolved = path.resolve(file);
  if (fs.existsSync(resolved)) return fs.realpathSync(resolved);
  const parent = path.dirname(resolved);
  if (parent === resolved) return resolved;
  return path.join(canonical(parent), path.basename(resolved));
}

function identity(file) {
  const resolved = canonical(file);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

function within(root, target) {
  const relative = path.relative(root, target);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function sameExistingFile(left, right) {
  if (!fs.existsSync(left) || !fs.existsSync(right)) return false;
  const a = fs.statSync(left, { bigint: true });
  const b = fs.statSync(right, { bigint: true });
  return a.ino !== 0n && a.ino === b.ino && a.dev === b.dev;
}

function validateOutput(file, inputs, library) {
  const output = path.resolve(file);
  if (path.extname(output).toLowerCase() !== '.json') throw new Error('--output must name a JSON report');
  const protectedPaths = [...inputs, ...library.sources.map((source) => source.path), __filename];
  if (library.profile) protectedPaths.push(library.profile.path);
  if (protectedPaths.some((protectedPath) => identity(protectedPath) === identity(output)
      || sameExistingFile(protectedPath, output))
      || within(identity(library.root), identity(output))) throw new Error('--output cannot overwrite an input, library or profile');
  if (fs.existsSync(output)) {
    const existing = readJson(output).value;
    if (existing.schema !== REPORT_SCHEMA) throw new Error('--output can replace only a prior expression scan report');
  }
  if (!fs.existsSync(path.dirname(output))) throw new Error('--output parent directory does not exist');
}

function printText(report, output) {
  process.stdout.write(`Expression library: ${report.library_version}; read-only diagnostics; human review required.\n`);
  for (const source of report.library_files) process.stdout.write(`Library: ${source.path} sha256=${source.sha256}\n`);
  if (report.profile) process.stdout.write(`Profile: ${report.profile.path} sha256=${report.profile.sha256}\n`);
  for (const input of report.inputs) process.stdout.write(`Input: ${input.file} sha256=${input.sha256}\n`);
  for (const finding of report.findings) {
    process.stdout.write(`${finding.file}:${finding.line}:${finding.column}: [${finding.severity}] ${finding.rule_id}`
      + ` chapter=${finding.chapter_title || '(untitled)'}: ${finding.reason}\n`
      + `  matched=${JSON.stringify(finding.matched)}\n  revision=${finding.revision}\n`
      + `  retain_when=${JSON.stringify(finding.retain_when)}\n`);
  }
  process.stdout.write(`Findings: ${report.findings.length}; manual checks not automatically evaluated: ${report.manual_checks.length}.\n`);
  for (const check of report.manual_checks) process.stdout.write(`Manual: ${check.rule_id}: ${check.reason}\n`);
  process.stdout.write(`Semantic policies requiring full-text human source review: ${report.semantic_checks.length}.\n`);
  for (const check of report.semantic_checks) {
    process.stdout.write(`Semantic: ${check.rule_id}: detector_coverage_partial=true; ${check.human_review_requirement}\n`);
  }
  if (output) process.stdout.write(`Report: ${path.resolve(output)}\n`);
}

try { process.exitCode = main(process.argv.slice(2)); }
catch (error) { process.stderr.write(`Expression scan error: ${error.message}\n`); process.exitCode = 2; }
