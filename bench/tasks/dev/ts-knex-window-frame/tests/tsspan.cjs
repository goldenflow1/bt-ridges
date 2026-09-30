// tsspan: compare one exported function between two TypeScript files.
//
//   node tsspan.cjs <original.ts> <candidate.ts> <functionName>
//
// Prints JSON: whether the text before/after the function and its header
// (leading JSDoc + signature up to the body) are byte-identical, plus counts
// of constructs inside the candidate's body.
const fs = require("node:fs");
const ts = require("/opt/task/tsparser/node_modules/typescript");

function locate(path, name) {
  const text = fs.readFileSync(path, "utf8");
  const sf = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const matches = sf.statements.filter(
    (s) => ts.isFunctionDeclaration(s) && s.name && s.name.text === name,
  );
  return { text, sf, matches };
}

const [originalPath, candidatePath, name] = process.argv.slice(2);
const original = locate(originalPath, name);
const candidate = locate(candidatePath, name);
const out = { found: candidate.matches.length, originalFound: original.matches.length };
if (out.found === 1 && out.originalFound === 1) {
  const o = original.matches[0];
  const c = candidate.matches[0];
  out.prefixEqual = original.text.slice(0, o.getFullStart()) === candidate.text.slice(0, c.getFullStart());
  out.suffixEqual = original.text.slice(o.getEnd()) === candidate.text.slice(c.getEnd());
  out.headerEqual =
    original.text.slice(o.getFullStart(), o.body.getStart()) ===
    candidate.text.slice(c.getFullStart(), c.body.getStart());
  out.bodyLength = c.getEnd() - c.getFullStart();
  out.nodes = 0;
  out.loops = 0;
  out.names = {};
  out.properties = {};
  out.taggedTemplates = 0;
  out.templateText = [];
  const visit = (node) => {
    out.nodes++;
    if (
      ts.isForStatement(node) || ts.isForInStatement(node) || ts.isForOfStatement(node) ||
      ts.isWhileStatement(node) || ts.isDoStatement(node)
    ) {
      out.loops++;
    }
    if (ts.isIdentifier(node)) {
      out.names[node.text] = (out.names[node.text] || 0) + 1;
    }
    if (ts.isPropertyAccessExpression(node)) {
      const p = node.name.text;
      out.properties[p] = (out.properties[p] || 0) + 1;
    }
    if (ts.isTaggedTemplateExpression(node)) {
      out.taggedTemplates++;
    }
    if (ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node) ||
        ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isStringLiteral(node)) {
      out.templateText.push(node.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(c.body);
}
process.stdout.write(JSON.stringify(out) + "\n");
