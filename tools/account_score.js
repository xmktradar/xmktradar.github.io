// 10-session follow-through for one account. Pure: no page, no prices.
// A call is already settled. ret is the stock's decimal return.
// xs is versus QQQ: stock minus QQQ when bullish, QQQ minus stock when bearish.
// A bullish win is a rising stock. A bearish win is a falling stock. Flat is not a win.
// scoreCalls is self-contained so a page can eval its source.
'use strict';

function scoreCalls(calls) {
  function block(side) {
    const rows = (calls || []).filter(c => c && c.side === side && typeof c.ret === 'number' && isFinite(c.ret));
    if (!rows.length) return null;
    const wins = rows.filter(c => (side === 'bear' ? c.ret < 0 : c.ret > 0)).length;
    const avg = rows.reduce((s, c) => s + c.ret, 0) / rows.length;
    const ex = rows.filter(c => typeof c.xs === 'number' && isFinite(c.xs));
    return {
      n: rows.length,
      wins,
      avg,
      avgXs: ex.length ? ex.reduce((s, c) => s + c.xs, 0) / ex.length : null,
    };
  }
  const bull = block('bull');
  const bear = block('bear');
  return { bull, bear, n: (bull ? bull.n : 0) + (bear ? bear.n : 0) };
}

module.exports = { scoreCalls };
