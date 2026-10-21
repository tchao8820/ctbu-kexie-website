/**
 * 站点渲染器 —— 浏览器与 Node 两端通用。
 *
 * 用法：
 *   浏览器：import { renderSite } from './tools/render.js'
 *   Node  ：node tools/render.js          打印到 stdout
 *            node tools/render.js --check  与 index.html 比对
 *
 * 模板语法（迷你 mustache），与 tools/build.py 保持一致：
 *   {{path}}             取值并转义
 *   {{$path}}            取值且不转义（$ 命名空间存放构建期生成的原始 HTML）
 *   {{#path}}…{{/path}}   区块：列表→逐项迭代，字典→压栈，字符串/布尔→条件
 *   {{^path}}…{{/path}}   反向区块
 *   {key}                派生值占位符（合计、获奖率等由明细算出）
 */

const DERIVED_KEYS = [
  'count', 'signupGroups', 'signupPeople', 'awardGroups', 'awardPeople',
  'rateByGroup', 'rateByPeople', 'memberCount', 'memberRatio',
  'topAwardGroups', 'topAwardPeople', 'topAwardRatio',
  'awardNationalSum', 'awardProvinceSum',
];

const MISSING = Symbol('missing');

/* ---------------------------------------------------------------- 模板引擎 */

function scan(tpl) {
  const out = [];
  let pos = 0;
  for (;;) {
    const start = tpl.indexOf('{{', pos);
    if (start < 0) { out.push(['text', tpl.slice(pos)]); return out; }
    if (start > pos) out.push(['text', tpl.slice(pos, start)]);
    const end = tpl.indexOf('}}', start);
    if (end < 0) throw new Error('模板中存在未闭合的 {{');
    const inner = tpl.slice(start + 2, end).trim();
    pos = end + 2;
    if (inner[0] === '#') out.push(['sec', inner.slice(1).trim()]);
    else if (inner[0] === '^') out.push(['inv', inner.slice(1).trim()]);
    else if (inner[0] === '/') out.push(['close', inner.slice(1).trim()]);
    else out.push(['var', inner]);
  }
}

function parse(toks, pos, stop) {
  const nodes = [];
  while (pos < toks.length) {
    const kind = toks[pos][0];
    if (kind === 'text' || kind === 'var') {
      nodes.push([kind, toks[pos][1]]);
      pos += 1;
    } else if (kind === 'sec' || kind === 'inv') {
      const name = toks[pos][1];
      const r = parse(toks, pos + 1, stop.concat([name]));
      nodes.push([kind, name, r.nodes]);
      pos = r.pos;
    } else {
      const name = toks[pos][1];
      if (stop.indexOf(name) >= 0) return { nodes, pos: pos + 1 };
      throw new Error('模板中出现未匹配的 {{/' + name + '}}');
    }
  }
  return { nodes, pos };
}

function resolve(frame, parts) {
  let cur = frame;
  for (const part of parts) {
    if (cur && typeof cur === 'object' && !Array.isArray(cur) &&
        Object.prototype.hasOwnProperty.call(cur, part)) {
      cur = cur[part];
    } else {
      return MISSING;
    }
  }
  return cur;
}

function lookup(ctx, path) {
  if (path[0] === '$') {
    const root = ctx[0]['$'] || {};
    const v = resolve(root, path.slice(1).split('.'));
    return v === MISSING ? '' : v;
  }
  const parts = path.split('.');
  for (let i = ctx.length - 1; i >= 0; i -= 1) {
    const v = resolve(ctx[i], parts);
    if (v !== MISSING) return v;
  }
  for (let i = ctx.length - 1; i >= 0; i -= 1) {
    for (let n = parts.length - 1; n > 0; n -= 1) {
      const v = resolve(ctx[i], parts.slice(0, n));
      if (v !== MISSING) {
        const rest = resolve(v, parts.slice(n));
        return rest === MISSING ? v : rest;
      }
    }
  }
  return '';
}

const ENTITY_RE = /&(?:#\d+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);/g;

function escapePlain(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  const text = String(value);
  let out = '';
  let last = 0;
  ENTITY_RE.lastIndex = 0;
  let m;
  while ((m = ENTITY_RE.exec(text)) !== null) {
    out += escapePlain(text.slice(last, m.index)) + m[0];
    last = m.index + m[0].length;
  }
  return out + escapePlain(text.slice(last));
}

function renderNodes(nodes, ctx) {
  let out = '';
  for (const node of nodes) {
    const kind = node[0];
    if (kind === 'text') out += node[1];
    else if (kind === 'var') {
      const path = node[1];
      const val = lookup(ctx, path);
      out += path[0] === '$' ? String(val) : escapeHtml(val);
    } else if (kind === 'sec') {
      const val = lookup(ctx, node[1]);
      if (Array.isArray(val)) {
        for (const item of val) out += renderNodes(node[2], ctx.concat([item]));
      } else if (val && typeof val === 'object') {
        out += renderNodes(node[2], ctx.concat([val]));
      } else if (val) {
        out += renderNodes(node[2], ctx);
      }
    } else if (kind === 'inv') {
      const val = lookup(ctx, node[1]);
      if (!val) out += renderNodes(node[2], ctx);
    }
  }
  return out;
}

/* ---------------------------------------------------------------- 派生值 */

function derive(data) {
  const rows = data.sections.results.rows;
  let signupGroups = 0, signupPeople = 0, awardGroups = 0, awardPeople = 0;
  for (const r of rows) {
    signupGroups += r.signupGroups;
    signupPeople += r.signupPeople;
    awardGroups += r.awardGroups;
    awardPeople += r.awardPeople;
  }
  const member = data.sections.member.kpis;
  const memberCount = Number(member[0].value);
  const memberFrom = Number(member[3].value);
  let top = rows[0];
  for (const r of rows) if (r.awardPeople > top.awardPeople) top = r;
  const historyAwards = data.sections.honors.awards;
  return {
    count: String(rows.length),
    signupGroups: String(signupGroups),
    signupPeople: String(signupPeople),
    awardGroups: String(awardGroups),
    awardPeople: String(awardPeople),
    rateByGroup: (awardGroups * 100 / signupGroups).toFixed(1),
    rateByPeople: (awardPeople * 100 / signupPeople).toFixed(1),
    memberCount: String(memberCount),
    memberRatio: (memberFrom * 100 / memberCount).toFixed(1),
    topAwardGroups: String(top.awardGroups),
    topAwardPeople: String(top.awardPeople),
    topAwardRatio: (top.awardPeople * 100 / awardPeople).toFixed(1),
    awardNationalSum: String(historyAwards.reduce((s, a) => s + a.national, 0)),
    awardProvinceSum: String(historyAwards.reduce((s, a) => s + a.province, 0)),
  };
}

function expand(node, derived) {
  if (typeof node === 'string') {
    return node.replace(/\{(count|signupGroups|signupPeople|awardGroups|awardPeople|rateByGroup|rateByPeople|memberCount|memberRatio|topAwardGroups|topAwardPeople|topAwardRatio|awardNationalSum|awardProvinceSum)\}/g,
      (m, key) => derived[key]);
  }
  if (Array.isArray(node)) return node.map((v) => expand(v, derived));
  if (node && typeof node === 'object') {
    const out = {};
    for (const key of Object.keys(node)) out[key] = expand(node[key], derived);
    return out;
  }
  return node;
}

function addHasFlags(node) {
  if (Array.isArray(node)) {
    node.forEach(addHasFlags);
  } else if (node && typeof node === 'object') {
    for (const key of Object.keys(node)) {
      const val = node[key];
      if (Array.isArray(val)) {
        node['has' + key[0].toUpperCase() + key.slice(1)] = val.length > 0;
        val.forEach(addHasFlags);
      } else {
        addHasFlags(val);
      }
    }
  }
  return node;
}

/* ---------------------------------------------------------------- 构件 */

function buildHead(data) {
  const site = data.site;
  const meta = data.meta;
  const url = site.url;
  const logo = url + site.logo;
  const attr = escapeHtml;
  const js = (v) => JSON.stringify(v);

  const lines = [
    '<title>' + attr(meta.title) + '</title>',
    '<meta name="description" content="' + attr(meta.description) + '">',
    '<meta name="keywords" content="' + attr(meta.keywords) + '">',
    '<meta property="og:title" content="' + attr(meta.ogTitle) + '">',
    '<meta property="og:description" content="' + attr(meta.ogDescription) + '">',
    '<meta property="og:type" content="website">',
    '<meta property="og:site_name" content="' + attr(meta.siteName) + '">',
    '<meta property="og:locale" content="zh_CN">',
    '<meta property="og:url" content="' + attr(url) + '">',
    '<meta property="og:image" content="' + attr(site.ogImage) + '">',
    '<meta property="og:image:width" content="1200">',
    '<meta property="og:image:height" content="630">',
    '<meta property="og:image:alt" content="' + attr(meta.ogImageAlt) + '">',
    '<meta name="twitter:card" content="summary_large_image">',
    '<meta name="twitter:title" content="' + attr(meta.ogTitle) + '">',
    '<meta name="twitter:description" content="' + attr(meta.ogDescription) + '">',
    '<meta name="twitter:image" content="' + attr(site.ogImage) + '">',
    '<meta name="robots" content="index,follow,max-image-preview:large">',
    '<meta name="author" content="' + attr(meta.author) + '">',
    '<meta name="theme-color" content="' + attr(meta.themeColor) + '">',
    '<link rel="canonical" href="' + attr(url) + '">',
    '<script type="application/ld+json">',
    '{',
    '  "@context": "https://schema.org",',
    '  "@graph": [',
    '    {',
    '      "@type": "Organization",',
    '      "@id": ' + js(url + '#org') + ',',
    '      "name": "重庆工商大学科技协会",',
    '      "alternateName": [' + meta.alternateNames.map(js).join(', ') + '],',
    '      "url": ' + js(url) + ',',
    '      "logo": ' + js(logo) + ',',
    '      "description": ' + js(meta.orgDescription) + ',',
    '      "foundingDate": "2002",',
    '      "parentOrganization": { "@type": "CollegeOrUniversity", "name": ' + js(meta.parentOrg) + ' },',
    '      "address": {',
    '        "@type": "PostalAddress",',
    '        "addressCountry": "CN",',
    '        "addressRegion": "重庆市",',
    '        "streetAddress": ' + js(meta.orgAddress),
    '      },',
    '      "contactPoint": [{',
    '        "@type": "ContactPoint",',
    '        "contactType": "招新咨询",',
    '        "telephone": ' + js(meta.telephone) + ',',
    '        "availableLanguage": ["zh-CN"]',
    '      }]',
    '    },',
    '    {',
    '      "@type": "WebSite",',
    '      "@id": ' + js(url + '#website') + ',',
    '      "name": "重庆工商大学科技协会官网",',
    '      "url": ' + js(url) + ',',
    '      "inLanguage": "zh-CN",',
    '      "publisher": { "@id": ' + js(url + '#org') + ' }',
    '    }',
    '  ]',
    '}',
    '</script>',
  ];
  return lines.join('\n');
}

function buildNavMob(nav) {
  let out = '\n';
  for (const link of nav.links) {
    out += '      <a href="' + escapeHtml(link.href) + '">' +
      escapeHtml(link.text) + '</a>\n';
  }
  out += '      <a class="nav-cta" href="' + escapeHtml(nav.cta.href) + '">' +
    escapeHtml(nav.cta.text) + '</a>\n    ';
  return out;
}

function buildResultsKpis(d) {
  return (
    '\n' +
    '      <div class="kpi"><b>' + d.count + '<i> 项</i></b><span>赛事项目</span></div>\n' +
    '      <div class="kpi"><b data-c="' + d.signupPeople + '">' + d.signupPeople + '</b>' +
    '<span>报名人次（' + d.signupGroups + ' 组）</span></div>\n' +
    '      <div class="kpi"><b data-c="' + d.awardPeople + '">' + d.awardPeople + '</b>' +
    '<span>获奖人次（' + d.awardGroups + ' 组）</span></div>\n' +
    '      <div class="kpi"><b data-c="' + d.rateByPeople + '" data-suffix="%">' +
    d.rateByPeople + '%</b><span>获奖率（按人次）</span></div>\n' +
    '    '
  );
}

function buildResultsNoscript(d) {
  return (
    '<noscript>\n' +
    '          <tr>\n' +
    '            <td colspan="6" style="font-size:13px;color:var(--sub);line-height:1.8">\n' +
    '              本表的' + d.count + ' 项赛事明细由脚本渲染，当前浏览器已禁用 JavaScript，因此无法显示。\n' +
    '              合计数据为：报名 ' + d.signupGroups + ' 组／' + d.signupPeople + ' 人次，' +
    '获奖 ' + d.awardGroups + ' 组／' + d.awardPeople + ' 人次，组获奖率 ' + d.rateByGroup + '%。\n' +
    '              启用 JavaScript 即可查看完整明细；也可联系协会获取《科创月统计表》原件。\n' +
    '            </td>\n' +
    '          </tr>\n' +
    '        </noscript>'
  );
}

function buildResultsTfoot(d) {
  return (
    '\n' +
    '          <tr>\n' +
    '            <td scope="row">合计（' + d.count + ' 项）</td>\n' +
    '            <td class="n">' + d.signupGroups + '</td>\n' +
    '            <td class="n">' + d.signupPeople + '</td>\n' +
    '            <td class="n">' + d.awardGroups + '</td>\n' +
    '            <td class="n">' + d.awardPeople + '</td>\n' +
    '            <td class="n">' + d.rateByGroup + '%</td>\n' +
    '          </tr>\n' +
    '        '
  );
}

function buildResultsJs(rows) {
  const lines = rows.map((row) => {
    const rate = row.awardGroups * 100 / row.signupGroups;
    return '[' + JSON.stringify(row.name) + ',' + row.signupGroups + ',' +
      row.signupPeople + ',' + row.awardGroups + ',' + row.awardPeople +
      ',' + rate.toFixed(1) + ']';
  });
  return 'var RESULTS=[\n' + lines.join(',\n') + '];';
}

/* ---------------------------------------------------------------- 主流程 */

export function renderSite(data, template) {
  const derived = derive(data);
  const d = addHasFlags(expand(data, derived));

  d['$'] = {
    head: buildHead(d),
    nav: { mob: buildNavMob(d.nav) },
    results: {
      kpis: buildResultsKpis(derived),
      noscript: buildResultsNoscript(derived),
      tfoot: buildResultsTfoot(derived),
      js: buildResultsJs(d.sections.results.rows),
    },
  };

  const toks = scan(template);
  const tree = parse(toks, 0, []).nodes;
  // 渲染后再展开一次：数据层在渲染前已展开，但模板里直接写的 {key}
  // （例如表格合计行）只有在这一步才会被替换，否则会原样穿到页面上。
  return expand(renderNodes(tree, [d]), derived);
}

export { derive, expand, addHasFlags, DERIVED_KEYS };

/* ---------------------------------------------------------------- Node 入口 */

if (typeof process !== 'undefined' && process.argv &&
    process.argv[1] && /render\.js$/.test(process.argv[1])) {
  const { readFileSync } = await import('node:fs');
  const { resolve, join, dirname } = await import('node:path');
  const { fileURLToPath } = await import('node:url');
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const data = JSON.parse(readFileSync(join(root, 'content', 'site.json'), 'utf8'));
  const template = readFileSync(join(root, 'tools', 'template.html'), 'utf8');
  const html = renderSite(data, template);
  if (process.argv.indexOf('--check') >= 0) {
    const cur = readFileSync(join(root, 'index.html'), 'utf8');
    process.stdout.write(cur === html ? 'index.html 与渲染器产物一致\n' : 'index.html 与渲染器产物不一致\n');
    process.exit(cur === html ? 0 : 1);
  }
  process.stdout.write(html);
}
