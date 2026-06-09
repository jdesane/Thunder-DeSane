(async function gcImport() {
  if (!location.hostname.includes('gc.com')) { alert('Use this on a GameChanger game page!'); return; }
  function wait(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }
  function getLines() { return document.body.innerText.split('\n').filter(function(l) { return l.trim(); }); }
  async function doScroll() {
    for (var si = 0; si < 3; si++) { window.scrollTo(0, si * document.body.scrollHeight / 2); await wait(120); }
    window.scrollTo(0, 0); await wait(150);
  }
  function sendToScout(combined) {
    function showAlert() {
      alert('Game data copied!\n\nSwitch to the Thunder Scout tab:\n1. Click "Add Game"\n2. Select "All Text" mode\n3. Cmd+V to paste\n4. Click Submit');
    }
    try {
      navigator.clipboard.writeText(combined).then(showAlert).catch(function() {
        var ta = document.createElement('textarea');
        ta.value = combined; ta.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(ta); ta.select(); document.execCommand('copy');
        document.body.removeChild(ta); showAlert();
      });
    } catch(e) {
      var ta = document.createElement('textarea');
      ta.value = combined; ta.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy');
      document.body.removeChild(ta); showAlert();
    }
  }
  var basePath = location.pathname.replace(/\/(box-score|plays|info|lineup|stats)\/?$/, '');
  var baseUrl = location.origin + basePath;
  var storageKey = 'ts_' + basePath;
  if (!basePath || basePath === '/') { alert('Could not detect game page. Make sure you are on a GameChanger game page.'); return; }
  if (location.href.includes('/plays')) {
    var savedBox = sessionStorage.getItem(storageKey);
    if (!savedBox) { alert('Please go to the Box Score tab and click the bookmarklet first.'); return; }
    await doScroll();
    var r = 10;
    while (document.body.innerText.indexOf('Top 1st') === -1 && document.body.innerText.indexOf('Bottom 1st') === -1 && r-- > 0) { await wait(700); }
    var sortBtn = Array.from(document.querySelectorAll('button,span,[role=button]')).find(function(el) { return el.textContent.trim() === 'Reverse Chronological'; });
    if (sortBtn) { sortBtn.click(); await wait(600); }
    await doScroll();
    var pl = getLines();
    var ps = pl.findIndex(function(l) { return l.trim() === 'Plays'; });
    if (ps === -1) ps = pl.findIndex(function(l) { return /^(Top|Bottom)\s+\d/.test(l.trim()); });
    var playsText = ps > -1 ? pl.slice(ps).join('\n') : pl.join('\n');
    sessionStorage.removeItem(storageKey);
    sendToScout('=== BOX SCORE ===\n' + savedBox + '\n\n=== PLAYS ===\n' + playsText);
    return;
  }
  if (!location.href.includes('/box-score')) {
    var boxL = Array.from(document.querySelectorAll('a')).find(function(a) { return a.href && a.href.includes('/box-score'); });
    if (boxL) { boxL.click(); } else { location.href = baseUrl + '/box-score'; }
    var ur = 10;
    while (!location.href.includes('/box-score') && ur-- > 0) { await wait(300); }
    await wait(600);
  }
  await doScroll();
  var retries = 12;
  while (document.body.innerText.indexOf('LINEUP') === -1 && retries-- > 0) {
    await wait(350);
    if (retries % 3 === 0) { await doScroll(); }
  }
  if (document.body.innerText.indexOf('LINEUP') === -1) {
    alert('Box score still loading. Make sure it is fully visible on screen, then click the bookmarklet again.'); return;
  }
  var boxText = getLines().join('\n');
  sessionStorage.setItem(storageKey, boxText);
  var plL = Array.from(document.querySelectorAll('a')).find(function(a) { return a.href && a.href.includes('/plays'); });
  if (plL) { plL.click(); } else { location.href = baseUrl + '/plays'; }
  var pr = 10;
  while (!location.href.includes('/plays') && pr-- > 0) { await wait(300); }
  await wait(600);
  await doScroll();
  var r2 = 10;
  while (document.body.innerText.indexOf('Top 1st') === -1 && document.body.innerText.indexOf('Bottom 1st') === -1 && r2-- > 0) { await wait(350); }
  if (document.body.innerText.indexOf('Top 1st') === -1 && document.body.innerText.indexOf('Bottom 1st') === -1) {
    alert('Plays tab still loading — click OK once the plays are visible on screen.');
    await doScroll();
    var r3 = 15;
    while (document.body.innerText.indexOf('Top 1st') === -1 && document.body.innerText.indexOf('Bottom 1st') === -1 && r3-- > 0) { await wait(400); }
    if (document.body.innerText.indexOf('Top 1st') === -1 && document.body.innerText.indexOf('Bottom 1st') === -1) {
      alert('Could not find plays data. Try navigating to the Plays tab manually and clicking the bookmarklet again.'); return;
    }
  }
  var sortBtn2 = Array.from(document.querySelectorAll('button,span,[role=button]')).find(function(el) { return el.textContent.trim() === 'Reverse Chronological'; });
  if (sortBtn2) { sortBtn2.click(); await wait(600); }
  await doScroll();
  var pl2 = getLines();
  var ps2 = pl2.findIndex(function(l) { return l.trim() === 'Plays'; });
  if (ps2 === -1) ps2 = pl2.findIndex(function(l) { return /^(Top|Bottom)\s+\d/.test(l.trim()); });
  var playsText2 = ps2 > -1 ? pl2.slice(ps2).join('\n') : pl2.join('\n');
  sessionStorage.removeItem(storageKey);
  sendToScout('=== BOX SCORE ===\n' + boxText + '\n\n=== PLAYS ===\n' + playsText2);
})();
