#!/usr/bin/env python3
"""Serve the Proof of Price read-only dashboard (Python standard library only)."""
from __future__ import annotations

import argparse
import html
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from statistics import median
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from binance_web3_rwa import RwaApiError, live_rwa_snapshot

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "monitor.sqlite3"
DEFAULT_UNIVERSE = BASE_DIR / "data" / "universe.json"
VENUES = ("ondo", "xstocks", "bstocks")
VENUE_LABELS = {"ondo": "Ondo", "xstocks": "xStocks", "bstocks": "bStocks"}

HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  __REFRESH_META__
  <meta name="theme-color" content="#0b1112">
  <title>Proof of Price — Tokenized Equity Monitor</title>
  <style>
    :root{color-scheme:dark;--bg:#0a1011;--panel:#10191a;--panel2:#132021;--line:#263638;--ink:#edf2ed;--muted:#95a7a3;--faint:#657572;--mint:#b6f27a;--teal:#57d9bd;--blue:#8fc7ff;--amber:#ffd078;--red:#ff8272;--white:#fff}
    *{box-sizing:border-box}html{background:var(--bg);scroll-behavior:smooth}body{margin:0;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.45;background:radial-gradient(ellipse at 84% -12%,rgba(87,217,189,.09),transparent 38%),linear-gradient(180deg,#0b1112 0%,#0a1011 100%)}
    .shell{width:min(1440px,calc(100% - 56px));margin:0 auto}.mono,.number,.ticker,.chip,.eyebrow,.tag,.stat-value,.bps,.table-head,.status-pill,.code{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;font-variant-numeric:tabular-nums}.chip{border:1px solid rgba(182,242,122,.26);border-radius:999px;padding:5px 8px;color:var(--mint);font-size:9px;letter-spacing:.08em;white-space:nowrap}
    header{height:72px;border-bottom:1px solid rgba(149,167,163,.16);display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{display:flex;align-items:center;gap:12px}.mark{height:34px;width:34px;border:1px solid rgba(182,242,122,.6);border-radius:11px;display:grid;place-items:center;color:var(--mint);font-weight:800;font-size:12px;letter-spacing:-1px;background:rgba(182,242,122,.07);box-shadow:0 0 24px rgba(182,242,122,.08)}.brand-name{font-size:12px;font-weight:800;letter-spacing:.15em}.brand-sub{display:block;color:var(--muted);font-size:9px;letter-spacing:.17em;margin-top:2px}.head-right{display:flex;align-items:center;gap:14px;color:var(--muted);font-size:11px}.live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--mint);box-shadow:0 0 0 4px rgba(182,242,122,.1);margin-right:7px}.head-sep{height:24px;width:1px;background:var(--line)}
    .hero{padding:52px 0 30px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(270px,.75fr);gap:38px;align-items:end}.eyebrow{color:var(--teal);font-size:10px;letter-spacing:.16em;text-transform:uppercase}.hero h1{font-size:clamp(36px,5vw,62px);line-height:1.02;letter-spacing:-.055em;margin:15px 0 16px;max-width:850px;font-weight:670}.hero h1 em{color:var(--mint);font-style:normal}.hero-copy{font-size:14px;color:#adbfba;max-width:710px;line-height:1.75}.hero-copy strong{color:var(--ink);font-weight:600}.hero-note{border:1px solid rgba(255,208,120,.28);background:linear-gradient(135deg,rgba(255,208,120,.08),rgba(255,208,120,.025));padding:19px 20px;border-radius:14px;position:relative;overflow:hidden}.hero-note:after{content:"";position:absolute;width:110px;height:110px;border:1px solid rgba(255,208,120,.12);border-radius:50%;right:-48px;top:-60px;box-shadow:0 0 0 18px rgba(255,208,120,.025),0 0 0 38px rgba(255,208,120,.02)}.hero-note .eyebrow{color:var(--amber)}.hero-note-title{font-size:15px;font-weight:650;margin:9px 0 4px}.hero-note p{font-size:11px;color:var(--muted);margin:0;max-width:370px;line-height:1.6}.hero-note .time{color:#fff0cd}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:10px 0 34px}.metric{border:1px solid var(--line);background:linear-gradient(150deg,rgba(19,32,33,.9),rgba(15,24,25,.94));border-radius:13px;padding:17px 18px;min-height:102px}.metric-label{font-size:10px;text-transform:uppercase;letter-spacing:.11em;color:var(--muted)}.metric-value{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:27px;letter-spacing:-.04em;margin-top:9px;font-weight:650}.metric-foot{font-size:10px;color:var(--faint);margin-top:2px}.metric.accent .metric-value{color:var(--mint)}.metric.warn .metric-value{color:var(--amber)}.metric.alert .metric-value{color:var(--red)}
    .basis-shell{display:grid;grid-template-columns:minmax(190px,.72fr) minmax(0,2fr);gap:18px;align-items:center;border:1px solid var(--line);background:linear-gradient(145deg,rgba(19,32,33,.82),rgba(15,24,25,.96));border-radius:14px;padding:18px}.basis-title{font-size:18px;letter-spacing:-.03em;margin:5px 0;color:var(--ink)}.basis-copy{font-size:10px;line-height:1.6;color:var(--muted);max-width:370px}.basis-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.basis-stat{border:1px solid var(--line);border-radius:10px;background:rgba(10,16,17,.34);padding:11px 12px;min-width:0}.basis-label{font-size:8px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}.basis-value{font:600 16px ui-monospace,monospace;letter-spacing:-.04em;margin-top:5px;color:var(--ink);white-space:nowrap}.basis-value.range{font-size:12px}.basis-foot{font-size:8px;color:var(--faint);margin-top:3px}.basis-leaders{grid-column:1/-1;display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:1px}.basis-leaders-label{font-size:8px;text-transform:uppercase;color:var(--faint);letter-spacing:.08em;margin-right:3px}.basis-chip{font:9px ui-monospace,monospace;padding:5px 7px;border:1px solid var(--line);border-radius:7px;background:var(--panel);white-space:nowrap}.basis-chip.above{color:var(--amber)}.basis-chip.below{color:var(--blue)}.basis-chart-title{font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-top:15px}.pairwise-chart-wrap{height:130px;margin-top:5px}.pairwise-cell{min-width:142px}@media(max-width:850px){.basis-shell{grid-template-columns:1fr}.basis-copy{max-width:none}}@media(max-width:560px){.basis-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.basis-shell{padding:13px}.basis-value{font-size:14px}.basis-value.range{font-size:11px}}
    .section{margin:0 0 34px}.section-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin:0 0 15px}.section-title{font-size:17px;letter-spacing:-.02em;margin:4px 0 0;font-weight:650}.section-desc{color:var(--muted);font-size:11px;margin-top:4px;max-width:760px}.section-kicker{font-size:9px;color:var(--faint);letter-spacing:.15em;text-transform:uppercase}
    .map-shell{border:1px solid var(--line);border-radius:15px;overflow:hidden;background:rgba(15,24,25,.88)}.controls{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 16px;border-bottom:1px solid var(--line);background:rgba(19,32,33,.56)}.filters{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.filter{border:1px solid transparent;background:transparent;color:var(--muted);padding:7px 10px;border-radius:8px;font:inherit;font-size:10px;cursor:pointer}.filter:hover,.filter.active{color:var(--ink);border-color:#334547;background:#1a292a}.filter.active{color:var(--mint)}.search{width:min(260px,45vw);border:1px solid #304143;background:#0b1314;color:var(--ink);border-radius:8px;padding:9px 11px;font:inherit;font-size:11px;outline:none}.search:focus{border-color:var(--teal);box-shadow:0 0 0 3px rgba(87,217,189,.08)}.search::placeholder{color:#71827f}.table-scroll{overflow:auto;max-height:680px}table{border-collapse:collapse;width:100%;min-width:1210px}.table-head th{position:sticky;top:0;background:#10191a;z-index:2;text-align:left;padding:11px 13px;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:#839692;font-weight:500;border-bottom:1px solid var(--line);white-space:nowrap}.table-head th:first-child{padding-left:17px}.data-row{border-bottom:1px solid rgba(38,54,56,.7);transition:background .14s;cursor:pointer}.data-row:hover{background:rgba(87,217,189,.045)}.data-row:last-child{border-bottom:0}.data-row td{padding:11px 13px;vertical-align:middle}.data-row td:first-child{padding-left:17px}.asset-name{font-size:12px;font-weight:700;letter-spacing:.02em}.asset-contract{font-size:9px;color:var(--faint);margin-top:3px}.reference-price{font-size:12px;font-weight:650}.reference-source{font-size:9px;color:var(--muted);margin-top:3px}.venue-cell{min-width:154px}.venue-price{font-size:11px;font-weight:650}.venue-gap{font-size:10px;margin-top:3px}.venue-gap.good{color:var(--teal)}.venue-gap.positive{color:var(--mint)}.venue-gap.negative{color:var(--blue)}.venue-gap.missing{color:var(--amber)}.venue-gap.incomplete{color:var(--red)}.venue-meta{font-size:9px;color:var(--faint);margin-top:2px}.quality{display:inline-flex;align-items:center;gap:6px;font-size:9px;letter-spacing:.05em;white-space:nowrap}.quality-dot{height:6px;width:6px;border-radius:50%;background:var(--teal)}.quality.outlier .quality-dot{background:var(--red);box-shadow:0 0 0 3px rgba(255,130,114,.1)}.quality.partial .quality-dot{background:var(--amber)}.quality-text{color:#c8d6d1}.quality-note{font-size:9px;color:var(--faint);margin-top:4px;max-width:180px}.empty{padding:26px;text-align:center;color:var(--muted);font-size:12px}
    .lower-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,.65fr);gap:14px}.panel{border:1px solid var(--line);border-radius:14px;background:linear-gradient(150deg,rgba(16,25,26,.98),rgba(13,21,22,.98));padding:17px 18px}.panel-head{display:flex;justify-content:space-between;align-items:start;gap:12px}.panel-title{font-size:13px;font-weight:650}.panel-sub{font-size:10px;color:var(--muted);margin-top:4px;line-height:1.55}.select{background:#0b1314;border:1px solid #344648;color:var(--ink);border-radius:7px;padding:7px 9px;font:inherit;font-size:10px}.chart-wrap{height:220px;position:relative;margin-top:12px}.chart{width:100%;height:100%;display:block}.chart-empty{position:absolute;inset:0;display:grid;place-items:center;text-align:center;color:var(--muted);font-size:11px;pointer-events:none}.chart-legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:10px;margin-top:4px}.legend-mark{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}.hist-note{font-size:9px;color:var(--faint);margin-top:8px}.issues{display:grid;gap:10px;margin-top:15px}.issue{display:grid;grid-template-columns:28px 1fr;gap:10px;align-items:start;padding:11px;border:1px solid rgba(38,54,56,.9);border-radius:10px;background:rgba(12,20,21,.65)}.issue-icon{width:25px;height:25px;display:grid;place-items:center;border-radius:8px;font:700 10px ui-monospace,monospace}.issue-icon.amber{color:var(--amber);background:rgba(255,208,120,.09)}.issue-icon.red{color:var(--red);background:rgba(255,130,114,.1)}.issue-icon.teal{color:var(--teal);background:rgba(87,217,189,.09)}.issue-title{font-size:10px;font-weight:650}.issue-copy{font-size:9px;color:var(--muted);margin-top:3px;line-height:1.55}.method{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px}.method-card{border:1px solid var(--line);border-radius:12px;background:rgba(15,24,25,.65);padding:16px}.formula{font:12px ui-monospace,monospace;color:var(--mint);padding:10px 12px;background:#0a1112;border-radius:8px;margin:12px 0;overflow:auto}.method-card p{color:var(--muted);font-size:10px;line-height:1.65;margin:7px 0 0}.method-card strong{color:#dce8e2;font-weight:600}.foot{border-top:1px solid var(--line);margin-top:34px;padding:17px 0 25px;display:flex;justify-content:space-between;gap:18px;color:var(--faint);font-size:9px}.foot .disclaimer{max-width:800px;line-height:1.6}.foot .version{white-space:nowrap}
    .live-api-card{border:1px solid var(--line);border-radius:12px;background:rgba(15,24,25,.65);padding:14px;margin-top:14px}.live-api-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.live-api-button{border:1px solid #d7ad00;border-radius:8px;background:#f0b90b;color:#181a20;padding:8px 11px;font:700 10px ui-monospace,monospace;cursor:pointer;white-space:nowrap}.live-api-button:disabled{opacity:.55;cursor:not-allowed}.live-api-output{margin:12px 0 0;padding:11px;border:1px solid var(--line);border-radius:8px;background:#fff;color:#1e2329;font:10px/1.65 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;min-height:48px}.live-api-note{font-size:9px;color:var(--muted);line-height:1.5;margin-top:8px}
    @media(max-width:900px){.shell{width:min(100% - 32px,1440px)}.hero{grid-template-columns:1fr;gap:18px;padding-top:38px}.hero-note{max-width:520px}.lower-grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:560px){.shell{width:calc(100% - 24px)}header{height:62px}.head-right .last-run,.head-sep{display:none}.hero{padding:30px 0 22px}.hero h1{font-size:38px}.metrics{gap:8px}.metric{padding:13px;min-height:90px}.metric-value{font-size:23px}.controls{align-items:stretch;flex-direction:column}.search{width:100%}.section-head{align-items:start;flex-direction:column}.method{grid-template-columns:1fr}.foot{flex-direction:column}}
  </style>
  <style id="binance-inspired-theme">
    :root{color-scheme:light;--bg:#f5f6f8;--panel:#fff;--panel2:#fff;--line:#e5e8ec;--ink:#1e2329;--muted:#5e6673;--faint:#89919d;--mint:#987000;--teal:#137d68;--blue:#4f6786;--amber:#916600;--red:#c6483d;--white:#fff}
    html,body{background:#f5f6f8!important;color:#1e2329!important}body{background:radial-gradient(ellipse at 84% -12%,rgba(240,185,11,.12),transparent 38%),linear-gradient(180deg,#fff 0%,#f5f6f8 100%)!important}
    header{background:rgba(255,255,255,.94);border-bottom:1px solid #e5e8ec!important}.mark{color:#f0b90b!important;background:#181a20!important;border-color:#181a20!important;box-shadow:0 5px 16px rgba(24,26,32,.12)!important}.brand-name{color:#1e2329}.brand-sub{color:#7d8590!important}.head-right{color:#606875!important}.live-dot{background:#f0b90b!important;box-shadow:0 0 0 4px rgba(240,185,11,.14)!important}.head-sep{background:#e2e6eb!important}.chip{border-color:rgba(240,185,11,.48)!important;color:#806000!important;background:#fffaf0}
    .eyebrow{color:#866300!important}.hero h1 em{color:#b18400!important}.hero-copy{color:#59616c!important}.hero-note{border-color:#ead58a!important;background:linear-gradient(135deg,#fff9e5,#fffdf6)!important;box-shadow:0 8px 24px rgba(139,105,0,.05)}.hero-note:after{border-color:rgba(240,185,11,.2)!important;box-shadow:0 0 0 18px rgba(240,185,11,.04),0 0 0 38px rgba(240,185,11,.025)!important}.hero-note .eyebrow{color:#9a7000!important}.hero-note p{color:#636b75!important}.hero-note .time{color:#604900!important}
    .metric{border-color:#e3e7eb!important;background:#fff!important;box-shadow:0 4px 20px rgba(30,35,41,.035)}.metric-label{color:#66707b!important}.metric-foot{color:#818a95!important}.metric.accent .metric-value{color:#9a7200!important}.metric.warn .metric-value{color:#986900!important}.metric.alert .metric-value{color:#c6483d!important}
    .basis-shell{background:linear-gradient(145deg,#fff,#fffdf6)!important;border-color:#e2e6ea!important;box-shadow:0 6px 24px rgba(30,35,41,.04)}.basis-title{color:#1e2329!important}.basis-copy{color:#626b76!important}.basis-stat{background:#fff!important;border-color:#e2e6ea!important}.basis-label{color:#727b86!important}.basis-value{color:#1e2329!important}.basis-foot{color:#828b96!important}.basis-chip{background:#fff!important;border-color:#e2e6ea!important}.basis-chip.above{color:#8f6900!important}.basis-chip.below{color:#4d6686!important}.basis-chart-title{color:#68717c!important}
    .section-kicker{color:#818995!important}.section-title{color:#1e2329}.section-desc{color:#68717c!important}.tag{color:#656e79!important}
    .map-shell{border-color:#e2e6ea!important;background:#fff!important;box-shadow:0 8px 28px rgba(30,35,41,.035)}.controls{border-color:#e7eaee!important;background:#fafbfc!important}.filter{color:#616a76!important}.filter:hover,.filter.active{border-color:#ead78e!important;background:#fff8df!important;color:#1e2329!important}.filter.active{color:#866100!important}.search{border-color:#d8dde3!important;background:#fff!important;color:#1e2329!important}.search:focus{border-color:#d5a800!important;box-shadow:0 0 0 3px rgba(240,185,11,.12)!important}.search::placeholder{color:#9299a3!important}.table-head th{background:#f7f8fa!important;color:#68717d!important;border-bottom-color:#e2e6ea!important}.data-row{border-bottom-color:#eceff2!important}.data-row:hover{background:rgba(240,185,11,.055)!important}.asset-contract{color:#8b939e!important}.reference-source{color:#6d7681!important}.venue-gap.good{color:#127b65!important}.venue-gap.positive{color:#8e6900!important}.venue-gap.negative{color:#4d6686!important}.venue-gap.missing{color:#916600!important}.venue-gap.incomplete{color:#c6483d!important}.venue-meta{color:#828b96!important}.quality-dot{background:#16836d!important}.quality.outlier .quality-dot{background:#d14f42!important;box-shadow:0 0 0 3px rgba(209,79,66,.1)!important}.quality.partial .quality-dot{background:#d09a00!important}.quality-text{color:#434b55!important}.quality-note{color:#7d8691!important}.empty{color:#68717c!important}
    .panel{border-color:#e2e6ea!important;background:#fff!important;box-shadow:0 8px 28px rgba(30,35,41,.035)}.panel-title{color:#1e2329}.panel-sub{color:#69727e!important}.select{background:#fff!important;border-color:#d8dde3!important;color:#1e2329!important}.chart-empty{color:#6a7380!important}.hist-note{color:#7e8792!important}.issues{color:#1e2329}.issue{border-color:#e8ebef!important;background:#fbfcfd!important}.issue-icon.amber{color:#896300!important;background:rgba(240,185,11,.14)!important}.issue-icon.red{color:#bd4237!important;background:rgba(198,72,61,.1)!important}.issue-icon.teal{color:#116f5b!important;background:rgba(19,125,104,.09)!important}.issue-title{color:#303741}.issue-copy{color:#68717c!important}
    .method-card{border-color:#e2e6ea!important;background:#fff!important}.formula{color:#775900!important;background:#fff8de!important}.method-card p{color:#68717c!important}.method-card strong{color:#2d343d!important}.foot{border-top-color:#e0e4e9!important;color:#717a85!important}.live-api-card{background:#fff!important;border-color:#e2e6ea!important;box-shadow:0 6px 18px rgba(30,35,41,.035)}.live-api-button{background:#f0b90b!important;color:#181a20!important;border-color:#e0ae00!important}.live-api-output{background:#fffdf5!important;border-color:#e7d79a!important;color:#27303a!important}.live-api-note{color:#68717c!important}.code{color:#4e5864}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand"><div class="mark">P/P</div><div><div class="brand-name">PROOF OF PRICE</div><span class="brand-sub">BSC · TOKENIZED EQUITY OBSERVATORY</span></div></div>
      <div class="head-right"><span><i class="live-dot"></i>PUBLIC DATA · BSC 56</span><span class="head-sep"></span><span class="last-run">LATEST SNAPSHOT <span class="mono">__ASOF__</span><span class="mono">__DURATION__</span></span><span class="chip">READ ONLY</span></div>
    </header>

    <section class="hero">
      <div>
        <div class="eyebrow">Market structure · BNB Hack 2026</div>
        <h1>A spread is only as good as its <em>reference.</em></h1>
        <p class="hero-copy">Tokenized equities trade on-chain while their source markets sleep. Proof of Price tracks cross-issuer prices <strong>per share</strong>—then shows when the comparison is missing, incomplete, or unexplained. A big number is not automatically a trade signal.</p>
      </div>
      <aside class="hero-note">
        <div class="eyebrow">Next high-value capture</div>
        <div class="hero-note-title">Final U.S. close before submission</div>
        <p><span class="time">Friday, 9 Oct · approx. 20:00 UTC</span><br>Watch the source quote stop updating while BSC tokens continue to move. This is a capture target—not an exchange timestamp guarantee.</p>
      </aside>
    </section>

    <section class="metrics" aria-label="Latest collector metrics">
      __METRICS__
    </section>

    <section class="section" aria-label="Direct token-to-token basis">
      <div class="basis-shell">
        <div><div class="section-kicker">Separate from reference-quote gaps · no stockInfo price required</div><h2 class="basis-title">bStocks ↔ Ondo</h2><div class="basis-copy">Each token price is normalized by its own sharesMultiplier. Positive means bStocks is higher than Ondo. This is a token-to-token observation only—fees, depth, slippage, and executable routes are not assessed.</div></div>
        <div class="basis-stats">__PAIRWISE_STATS__</div>
        <div class="basis-leaders">__PAIRWISE_TOP__</div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div><div class="section-kicker">01 / cross-issuer coverage</div><h2 class="section-title">Price integrity map</h2><div class="section-desc">Per-share source-quote gaps plus a separately labeled bStocks↔Ondo token basis. The basis does not use or imply an underlying reference quote. Select a row to load both histories; |gap| ≥ 1,000 bp is a review flag, not a trade trigger.</div></div>
        <div class="tag">BSC CHAIN 56 · 38 TICKERS · 3 REPRESENTATIONS</div>
      </div>
      <div class="map-shell">
        <div class="controls">
          <div class="filters"><button class="filter active" data-filter="all">All tickers</button><button class="filter" data-filter="outliers">Large reference gaps</button><button class="filter" data-filter="gaps">Incomplete feeds</button></div>
          <input class="search" id="ticker-search" type="search" placeholder="Filter by ticker…" aria-label="Filter tickers">
        </div>
        <div class="table-scroll"><table><thead class="table-head"><tr><th>Ticker</th><th>Underlying field (reported)</th><th>Ondo vs reference</th><th>xStocks vs reference</th><th>bStocks vs reference</th><th>bStocks ↔ Ondo basis</th><th>Integrity state</th></tr></thead><tbody id="ticker-rows">__ROWS__</tbody></table></div>
        <div class="empty" id="empty-state" hidden>No tickers match this filter.</div>
      </div>
    </section>

    <section class="section lower-grid">
      <div class="panel">
        <div class="panel-head"><div><div class="section-kicker">02 / time series</div><div class="panel-title">Reference-quote gap history</div><div class="panel-sub">Only rows with both token metrics and a source quote are plotted. The logarithmic y-scale keeps isolated outliers from flattening every other series.</div></div><select class="select" id="history-ticker" aria-label="Select ticker for history">__OPTIONS__</select></div>
        <div class="chart-wrap"><canvas class="chart" id="history-chart"></canvas><div class="chart-empty" id="chart-empty">Loading observations…</div></div>
        <div class="chart-legend"><span><i class="legend-mark" style="background:#f0b90b"></i>Ondo vs reference</span><span><i class="legend-mark" style="background:#343a40"></i>xStocks vs reference</span><span><i class="legend-mark" style="background:#5b8f75"></i>bStocks vs reference</span></div>
        <div class="hist-note" id="history-note">Reference-quote comparisons. Times are UTC; these are poll times, not exchange-published quote timestamps.</div>
        <div class="basis-chart-title">Direct token-to-token basis · bStocks vs Ondo · no underlying quote</div>
        <div class="chart-wrap pairwise-chart-wrap"><canvas class="chart" id="pairwise-chart"></canvas><div class="chart-empty" id="pairwise-empty">Loading pairwise history…</div></div>
        <div class="hist-note" id="pairwise-note">Positive means bStocks per-share token price is above Ondo. No route costs, liquidity, or slippage checks.</div>
      </div>
      <div class="panel">
        <div class="section-kicker">03 / what the feed says</div><div class="panel-title" style="margin-top:4px">Data quality is part of the product</div><div class="panel-sub">The monitor keeps missing values visible instead of manufacturing a spread.</div>
        <div class="live-api-card">
          <div class="live-api-head"><div><div class="section-kicker">Live · signed · read-only</div><div class="panel-title" style="margin-top:4px">Official RWA API check</div></div><button class="live-api-button" id="live-fetch" type="button">Fetch selected ticker</button></div>
          <div class="panel-sub" style="margin-top:7px">Fetch current BSC token data for the selected ticker. API credentials stay on this server; no wallet or trade is involved.</div>
          <pre class="live-api-output" id="live-result" aria-live="polite">Choose a ticker above, then fetch a live read.</pre>
          <div class="live-api-note">Live API readings are separate from the saved historical polls. Reported referencePrice is not an independent stock-market quote.</div>
        </div>
        <div class="section-kicker" style="margin-top:15px">Largest reference-quote gaps · review only</div>
        <div class="issues">__TOP__</div>
        <div class="section-kicker" style="margin-top:18px">Baseline feed findings</div>
        <div class="issues">
          <div class="issue"><div class="issue-icon amber">38</div><div><div class="issue-title">bStocks underlying field missing</div><div class="issue-copy">The dynamic endpoint returned <span class="code">stockInfo.price=null</span> for all 38 bStocks in the baseline. No bStocks-vs-reference gap is claimed.</div></div></div>
          <div class="issue"><div class="issue-icon red">11</div><div><div class="issue-title">xStocks token price absent</div><div class="issue-copy">The baseline had a multiplier but no <span class="code">tokenInfo.price</span> for 11 xStocks: ADBE, ASML, ASTS, BMNR, CRM, EWY, GS, HIMS, IREN, PYPL, SOXL.</div></div></div>
          <div class="issue"><div class="issue-icon teal">!</div><div><div class="issue-title">Source status fields can disagree</div><div class="issue-copy">A Sunday AAPL Ondo response said <span class="code">marketStatus=offhours</span> and <span class="code">openState=true</span>. The app preserves these as source fields; it does not infer U.S. market hours from <span class="code">openState</span>.</div></div></div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head"><div><div class="section-kicker">04 / measurement contract</div><h2 class="section-title">Normalize first. Qualify the reference. Then compare.</h2></div></div>
      <div class="method">
        <div class="method-card"><div class="section-kicker">Per-share basis</div><div class="formula">per_share = tokenInfo.price / tokenInfo.sharesMultiplier<br>gap_bp = (per_share / stockInfo.price − 1) × 10,000</div><p>The corporate-action multiplier is applied before calculating the basis-point gap. A null, zero, or missing value is not silently coerced into a price.</p></div>
        <div class="method-card"><div class="section-kicker">Provenance guard</div><p><strong>The official RWA API's <span class="code">referencePrice</span> is documented as derived from the on-chain token price.</strong> It is not an independent stock quote. The separate <span class="code">stockInfo.price</span> field is shown as reported, but this monitor does not assume its independence; the observed source fields, time, and gaps remain visible for review.</p></div>
        <div class="method-card"><div class="section-kicker">Direct venue-to-venue basis</div><div class="formula">pair_bp = (bStocks/share ÷ Ondo/share − 1) × 10,000</div><p>This uses two normalized token prices and does not require <span class="code">stockInfo.price</span>. It is separate from each venue's reference-quote gap and is not evidence of executable arbitrage.</p></div>
      </div>
    </section>

    <footer class="foot"><div class="disclaimer">READ-ONLY RESEARCH TOOL · Not financial advice and not an execution venue. A displayed gap does not establish liquidity, executable pricing, or profit. Large discrepancies may reflect stale data, missing share ratios, or API limitations.</div><div class="version">SNAPSHOT __ASOF__ · __REFRESH_LABEL__</div></footer>
  </div>
  <script id="page-data" type="application/json">__JSON__</script>
  <script>
    (()=>{
      const pageData=JSON.parse(document.getElementById('page-data').textContent);
      const rows=[...document.querySelectorAll('.data-row')];
      const search=document.getElementById('ticker-search');
      const empty=document.getElementById('empty-state');
      let activeFilter='all';
      function applyFilters(){
        const q=search.value.trim().toUpperCase();let visible=0;
        rows.forEach(row=>{
          const matchText=!q||row.dataset.ticker.includes(q);
          const matchType=activeFilter==='all'||(activeFilter==='outliers'&&row.dataset.outlier==='1')||(activeFilter==='gaps'&&row.dataset.gap==='1');
          const show=matchText&&matchType;row.hidden=!show;if(show)visible++;
        });empty.hidden=visible!==0;
      }
      search.addEventListener('input',applyFilters);
      document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.filter').forEach(b=>b.classList.remove('active'));btn.classList.add('active');activeFilter=btn.dataset.filter;applyFilters()}));

      const select=document.getElementById('history-ticker');
      const canvas=document.getElementById('history-chart');
      const emptyChart=document.getElementById('chart-empty');
      const note=document.getElementById('history-note');
      const pairCanvas=document.getElementById('pairwise-chart');
      const pairEmpty=document.getElementById('pairwise-empty');
      const pairNote=document.getElementById('pairwise-note');
      const liveButton=document.getElementById('live-fetch');
      const liveResult=document.getElementById('live-result');
      if(pageData.static_preview){liveButton.disabled=true;liveResult.textContent='This is an offline snapshot. Live API checks are available only when the dashboard is running on your private local server.'}
      const colors={ondo:'#f0b90b',xstocks:'#343a40',bstocks:'#5b8f75'};
      const labels={ondo:'Ondo',xstocks:'xStocks',bstocks:'bStocks'};
      function fmtBps(v){return (v>0?'+':'')+new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(v)+' bp'}
      function drawPairwise(history){
        const rect=pairCanvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
        if(!rect.width)return;
        pairCanvas.width=Math.round(rect.width*dpr);pairCanvas.height=Math.round(rect.height*dpr);
        const ctx=pairCanvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
        const w=rect.width,h=rect.height;ctx.clearRect(0,0,w,h);
        const points=history.pairwise||[];
        if(!points.length){pairEmpty.textContent='No valid bStocks↔Ondo pair for this ticker yet.';pairEmpty.hidden=false;pairNote.textContent='Both venues need valid normalized token prices; an underlying stock quote is not required.';return}
        pairEmpty.hidden=true;
        const left=54,right=12,top=10,bottom=25,pw=w-left-right,ph=h-top-bottom;
        const maxAbs=Math.max(1,...points.map(p=>Math.abs(p.basis_bps||0))),scale=Math.log1p(maxAbs);
        const y=value=>top+ph/2-(Math.sign(value)*Math.log1p(Math.abs(value))/scale)*(ph/2-5);
        const times=points.map(p=>Date.parse(p.completed_at_utc)).filter(Number.isFinite);
        const minT=Math.min(...times),maxT=Math.max(...times);
        const x=p=>left+(maxT===minT?pw/2:((Date.parse(p.completed_at_utc)-minT)/(maxT-minT))*pw);
        ctx.font='9px ui-monospace,monospace';ctx.lineWidth=1;
        [-maxAbs,0,maxAbs].forEach(val=>{const yy=y(val);ctx.strokeStyle=val===0?'#b7bdc5':'#e7eaee';ctx.setLineDash(val===0?[]:[3,5]);ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#727b86';ctx.textAlign='right';ctx.fillText(val===0?'0 bp':fmtBps(val),left-7,yy+3)});
        ctx.strokeStyle='#9a7200';ctx.fillStyle='#9a7200';ctx.lineWidth=1.8;ctx.beginPath();
        points.forEach((p,i)=>{const xx=x(p),yy=y(p.basis_bps);if(i===0)ctx.moveTo(xx,yy);else ctx.lineTo(xx,yy)});ctx.stroke();
        points.forEach(p=>{ctx.beginPath();ctx.arc(x(p),y(p.basis_bps),2.8,0,Math.PI*2);ctx.fill()});
        ctx.fillStyle='#727b86';ctx.textAlign='left';ctx.fillText(new Date(minT).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit'})+' UTC',left,h-6);
        ctx.textAlign='right';ctx.fillText(new Date(maxT).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit'})+' UTC',w-right,h-6);
        pairNote.textContent=history.ticker+' · '+points.length+' pairwise observations · '+points[0].completed_at_utc+' → '+points[points.length-1].completed_at_utc+' · positive = bStocks above Ondo.';
      }
      function draw(history){
        drawPairwise(history);
        const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
        if(!rect.width){return}
        canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr);
        const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
        const w=rect.width,h=rect.height;ctx.clearRect(0,0,w,h);
        const points=history.observations||[];
        if(!points.length){emptyChart.textContent='No comparable observations for this ticker yet.';emptyChart.hidden=false;note.textContent='Missing reference or incomplete token metrics; no zero-valued gap is plotted.';return}
        emptyChart.hidden=true;
        const left=54,right=12,top=12,bottom=28,pw=w-left-right,ph=h-top-bottom;
        const maxAbs=Math.max(1,...points.map(p=>Math.abs(p.spread_bps||0)));
        const scale=Math.log1p(maxAbs);
        const y=value=>top+ph/2-(Math.sign(value)*Math.log1p(Math.abs(value))/scale)*(ph/2-5);
        const times=points.map(p=>Date.parse(p.fetched_at_utc)).filter(Number.isFinite);
        const minT=Math.min(...times),maxT=Math.max(...times);
        const x=p=>left+(maxT===minT?pw/2:((Date.parse(p.fetched_at_utc)-minT)/(maxT-minT))*pw);
        ctx.font='9px ui-monospace,monospace';ctx.lineWidth=1;
        [-maxAbs,0,maxAbs].forEach(val=>{const yy=y(val);ctx.strokeStyle=val===0?'#b7bdc5':'#e7eaee';ctx.setLineDash(val===0?[]:[3,5]);ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#727b86';ctx.textAlign='right';ctx.fillText(val===0?'0 bp':fmtBps(val),left-7,yy+3)});
        Object.keys(colors).forEach(venue=>{
          const series=points.filter(p=>p.venue===venue&&p.spread_bps!==null);
          if(!series.length)return;
          ctx.strokeStyle=colors[venue];ctx.fillStyle=colors[venue];ctx.lineWidth=1.8;ctx.beginPath();
          series.forEach((p,i)=>{const xx=x(p),yy=y(p.spread_bps);if(i===0)ctx.moveTo(xx,yy);else ctx.lineTo(xx,yy)});ctx.stroke();
          series.forEach(p=>{ctx.beginPath();ctx.arc(x(p),y(p.spread_bps),2.6,0,Math.PI*2);ctx.fill()});
        });
        ctx.fillStyle='#727b86';ctx.textAlign='left';ctx.fillText(new Date(minT).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit'})+' UTC',left,h-7);
        ctx.textAlign='right';ctx.fillText(new Date(maxT).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit'})+' UTC',w-right,h-7);
        const first=points[0],last=points[points.length-1];
        note.textContent=history.ticker+' · '+points.length+' comparable observations · '+first.fetched_at_utc+' → '+last.fetched_at_utc+' · timestamps are our poll times, not publisher quote timestamps.';
      }
      async function loadHistory(ticker){
        emptyChart.textContent='Loading observations…';emptyChart.hidden=false;
        pairEmpty.textContent='Loading pairwise history…';pairEmpty.hidden=false;
        if(pageData.histories&&Object.prototype.hasOwnProperty.call(pageData.histories,ticker)){draw(pageData.histories[ticker]);return}
        try{const response=await fetch('/api/history?ticker='+encodeURIComponent(ticker),{cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);draw(await response.json())}
        catch(e){emptyChart.textContent='History endpoint unavailable.';emptyChart.hidden=false;pairEmpty.textContent='Pairwise history endpoint unavailable.';pairEmpty.hidden=false;note.textContent=String(e);pairNote.textContent=String(e)}
      }
      select.addEventListener('change',()=>loadHistory(select.value));
      liveButton.addEventListener('click',async()=>{
        const ticker=select.value;
        liveButton.disabled=true;
        liveResult.textContent='Requesting signed read-only RWA data for '+ticker+'…';
        const money=value=>{const n=Number(value);return value===null||value===undefined||!Number.isFinite(n)?'missing':'$'+n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:6})};
        const utc=value=>value||'not supplied by API';
        const venueLine=(label,item)=>item?label+': '+(item.symbol||'token')+' · '+money(item.per_share_usd)+'/share · API price updated '+utc(item.token_price_updated_at_utc):label+': not returned';
        try{
          const response=await fetch('/api/live-rwa?ticker='+encodeURIComponent(ticker),{cache:'no-store'});
          const data=await response.json();
          if(!response.ok)throw new Error(data.error||('HTTP '+response.status));
          const basis=data.direct_basis_bps===null?null:Number(data.direct_basis_bps);
          const basisText=basis===null||!Number.isFinite(basis)?'not computable (a venue value is missing)':(basis>0?'+':'')+basis.toFixed(2)+' bp';
          const bs=data.venues&&data.venues.bstocks, ondo=data.venues&&data.venues.ondo;
          liveResult.textContent=[
            'LIVE API READ · '+data.ticker+' · BSC '+data.chain_id+' · '+data.status.toUpperCase(),
            venueLine('bStocks',bs),
            venueLine('Ondo',ondo),
            'Direct bStocks↔Ondo basis: '+basisText,
            'Fetched by this server: '+utc(data.completed_at_utc),
            'Market status fields (reported): bStocks '+(bs&&bs.market_status||'not supplied')+' · Ondo '+(ondo&&ondo.market_status||'not supplied'),
            'Requests: '+data.request_count+' signed read-only API calls · no wallet transaction'
          ].join(String.fromCharCode(10));
        }catch(error){
          liveResult.textContent='Live read unavailable: '+String(error.message||error)+String.fromCharCode(10)+'Check that the local server has valid credentials and try again. No credential value is shown here.';
        }finally{liveButton.disabled=Boolean(pageData.static_preview)}
      });
      rows.forEach(row=>row.addEventListener('click',()=>{select.value=row.dataset.ticker;loadHistory(select.value);document.querySelector('.lower-grid').scrollIntoView({behavior:'smooth',block:'start'})}));
      loadHistory(select.value);
      window.addEventListener('resize',()=>loadHistory(select.value));
    })();
  </script>
</body>
</html>'''


def connect_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def normalized_pair_basis_bps(bstocks_per_share: Any, ondo_per_share: Any) -> float | None:
    """Compare normalized bStocks and Ondo token prices without an underlying quote."""
    bstocks = _safe_float(bstocks_per_share)
    ondo = _safe_float(ondo_per_share)
    if (bstocks is None or ondo is None or not math.isfinite(bstocks)
            or not math.isfinite(ondo) or bstocks <= 0 or ondo <= 0):
        return None
    basis = (bstocks / ondo - 1.0) * 10_000
    return basis if math.isfinite(basis) else None


def _poll_seconds(started: str | None, completed: str | None) -> float | None:
    if not started or not completed:
        return None
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        return max(0.0, (end - start).total_seconds())
    except ValueError:
        return None


def latest_snapshot(db_path: Path, universe_path: Path = DEFAULT_UNIVERSE) -> dict[str, Any]:
    with connect_db(db_path) as connection:
        poll = connection.execute(
            "SELECT * FROM polls WHERE completed_at_utc IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if poll is None:
            raise RuntimeError("No completed poll is available yet")
        observations = connection.execute(
            "SELECT * FROM observations WHERE poll_id=? ORDER BY ticker, venue",
            (poll["id"],),
        ).fetchall()
        by_ticker: dict[str, dict[str, dict[str, Any]]] = {}
        for obs in observations:
            item = dict(obs)
            by_ticker.setdefault(item["ticker"], {})[item["venue"]] = item

        try:
            universe_doc = json.loads(universe_path.read_text(encoding="utf-8"))
            universe_tickers = list(universe_doc.get("tickers", {}).keys())
        except (OSError, json.JSONDecodeError, AttributeError):
            universe_tickers = sorted(by_ticker)

        ticker_rows: list[dict[str, Any]] = []
        flat_gaps: list[dict[str, Any]] = []
        pairwise_rows: list[dict[str, Any]] = []
        for ticker in universe_tickers:
            reps = by_ticker.get(ticker, {})
            venues: dict[str, Any] = {}
            gaps: list[float] = []
            missing_fields: list[str] = []
            incomplete_fields: list[str] = []
            failed_fields: list[str] = []
            for venue in VENUES:
                obs = reps.get(venue)
                if obs is None:
                    venues[venue] = None
                    incomplete_fields.append(venue)
                    continue
                item = {
                    "symbol": obs["symbol"],
                    "status": obs["status"],
                    "reference_state": obs["reference_state"],
                    "token_price": _safe_float(obs["token_price"]),
                    "shares_multiplier": _safe_float(obs["shares_multiplier"]),
                    "stock_price": _safe_float(obs["stock_price"]),
                    "per_share_price": _safe_float(obs["per_share_price"]),
                    "spread_bps": _safe_float(obs["spread_bps"]),
                    "market_status": obs["market_status"],
                    "api_open_state": obs["api_open_state"],
                    "fetched_at_utc": obs["fetched_at_utc"],
                    "latency_ms": _safe_float(obs["latency_ms"]),
                    "error": obs["error"],
                    "raw_excerpt": obs["raw_excerpt"],
                }
                venues[venue] = item
                if item["spread_bps"] is not None:
                    gaps.append(item["spread_bps"])
                    flat_gaps.append({
                        "ticker": ticker,
                        "venue": venue,
                        "venue_label": VENUE_LABELS[venue],
                        "spread_bps": item["spread_bps"],
                        "per_share_price": item["per_share_price"],
                    })
                if item["status"] == "ok" and item["reference_state"] == "missing":
                    missing_fields.append(venue)
                elif item["status"] == "incomplete_metrics":
                    incomplete_fields.append(venue)
                elif item["status"] in ("request_error", "api_error", "invalid_payload"):
                    failed_fields.append(venue)

            pairwise_basis = None
            bstocks_item = venues.get("bstocks")
            ondo_item = venues.get("ondo")
            if (bstocks_item and ondo_item and bstocks_item["status"] == "ok"
                    and ondo_item["status"] == "ok"):
                pairwise_basis = normalized_pair_basis_bps(
                    bstocks_item["per_share_price"], ondo_item["per_share_price"]
                )
            if pairwise_basis is not None:
                pairwise_rows.append({
                    "ticker": ticker,
                    "basis_bps": pairwise_basis,
                    "bstocks_per_share": bstocks_item["per_share_price"],
                    "ondo_per_share": ondo_item["per_share_price"],
                })

            quote = next((venues[v] for v in ("ondo", "xstocks")
                          if venues.get(v) and venues[v].get("stock_price") is not None), None)
            quote_value = quote.get("stock_price") if quote else None
            max_abs_gap = max((abs(gap) for gap in gaps), default=None)
            if max_abs_gap is not None and max_abs_gap >= 1000:
                integrity_state = "UNEXPLAINED GAP"
                integrity_class = "outlier"
                integrity_note = "Large comparison; not validated as executable"
            elif incomplete_fields or missing_fields or failed_fields:
                integrity_state = "PARTIAL DATA"
                integrity_class = "partial"
                reasons = []
                if missing_fields:
                    reasons.append("reference absent: " + ", ".join(VENUE_LABELS[v] for v in missing_fields))
                if incomplete_fields:
                    reasons.append("incomplete: " + ", ".join(VENUE_LABELS[v] for v in incomplete_fields))
                if failed_fields:
                    reasons.append("request failed: " + ", ".join(VENUE_LABELS[v] for v in failed_fields))
                integrity_note = "; ".join(reasons)
            else:
                integrity_state = "GAPS MEASURED"
                integrity_class = "measured"
                integrity_note = "Fields present; independence/liquidity still require review"
            ticker_rows.append({
                "ticker": ticker,
                "venues": venues,
                "source_quote": quote_value,
                "quote_source": next((v for v in ("ondo", "xstocks")
                                       if venues.get(v) and venues[v].get("stock_price") is not None), None),
                "pairwise_basis_bps": pairwise_basis,
                "max_abs_gap_bps": max_abs_gap,
                "integrity_state": integrity_state,
                "integrity_class": integrity_class,
                "integrity_note": integrity_note,
                "has_gap": bool(gaps),
                # The all-venue bStocks-null issue is systemic and already shown on every row;
                # this filter isolates incomplete token metrics or no usable source field.
                "has_issue": bool(incomplete_fields or failed_fields or quote_value is None),
            })
        ticker_rows.sort(key=lambda row: (row["max_abs_gap_bps"] is not None,
                                          row["max_abs_gap_bps"] or -1), reverse=True)
        flat_gaps.sort(key=lambda row: abs(row["spread_bps"]), reverse=True)
        pairwise_rows.sort(key=lambda row: abs(row["basis_bps"]), reverse=True)
        pairwise_values = [row["basis_bps"] for row in pairwise_rows]
        pairwise_summary = {
            "pair_count": len(pairwise_rows),
            "universe_count": len(universe_tickers),
            "median_bps": median(pairwise_values) if pairwise_values else None,
            "min_bps": min(pairwise_values) if pairwise_values else None,
            "max_bps": max(pairwise_values) if pairwise_values else None,
            # Avoid classifying exact 100 bp as over threshold due to float residue.
            "over_100_bps": sum(abs(value) > 100.0 + 1e-9 for value in pairwise_values),
            "top": pairwise_rows[:3],
        }

        status_counts = Counter(
            row["market_status"] for row in by_ticker.get("AAPL", {}).values()
            if row.get("market_status")
        )
        return {
            "poll": dict(poll),
            "poll_seconds": _poll_seconds(poll["started_at_utc"], poll["completed_at_utc"]),
            "tickers": ticker_rows,
            "top_gaps": flat_gaps[:6],
            "pairwise_basis": pairwise_summary,
            "market_status_counts": dict(status_counts),
            "universe_count": len(universe_tickers),
            "observation_count": len(observations),
        }


def history_for_ticker(db_path: Path, ticker: str, limit: int = 240) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    with connect_db(db_path) as connection:
        allowed = {row[0] for row in connection.execute("SELECT DISTINCT ticker FROM observations")}
        if ticker not in allowed:
            raise ValueError("Unknown ticker")
        rows = connection.execute(
            """SELECT ticker, venue, fetched_at_utc, spread_bps, stock_price,
                      per_share_price, status, reference_state
               FROM (
                   SELECT o.ticker, o.venue, o.fetched_at_utc, o.spread_bps,
                          o.stock_price, o.per_share_price, o.status, o.reference_state
                   FROM observations o JOIN polls p ON p.id=o.poll_id
                   WHERE o.ticker=? AND p.completed_at_utc IS NOT NULL
                     AND o.spread_bps IS NOT NULL
                   ORDER BY o.fetched_at_utc DESC LIMIT ?
               ) ORDER BY fetched_at_utc ASC""",
            (ticker, limit),
        ).fetchall()
        pair_rows = connection.execute(
            """SELECT p.id AS poll_id, p.completed_at_utc,
                      b.per_share_price AS bstocks_per_share,
                      o.per_share_price AS ondo_per_share,
                      b.status AS bstocks_status, o.status AS ondo_status
               FROM polls p
               JOIN observations b ON b.poll_id=p.id AND b.ticker=? AND b.venue='bstocks'
               JOIN observations o ON o.poll_id=p.id AND o.ticker=? AND o.venue='ondo'
               WHERE p.completed_at_utc IS NOT NULL
               ORDER BY p.id DESC LIMIT ?""",
            (ticker, ticker, limit),
        ).fetchall()
        pairwise_points = []
        for row in reversed(pair_rows):
            if row["bstocks_status"] != "ok" or row["ondo_status"] != "ok":
                continue
            basis = normalized_pair_basis_bps(row["bstocks_per_share"], row["ondo_per_share"])
            if basis is not None:
                pairwise_points.append({
                    "ticker": ticker,
                    "poll_id": row["poll_id"],
                    "completed_at_utc": row["completed_at_utc"],
                    "basis_bps": basis,
                    "bstocks_per_share": row["bstocks_per_share"],
                    "ondo_per_share": row["ondo_per_share"],
                })
        return {
            "ticker": ticker,
            "observations": [dict(row) for row in rows],
            "pairwise": pairwise_points,
        }


def _money(value: Any) -> str:
    number = _safe_float(value)
    return "—" if number is None else "$" + format(number, ",.2f")


def _bps(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "—"
    digits = 0 if abs(number) >= 1000 else 1
    return f"{number:+,.{digits}f} bp"


def _venue_cell(venue: str, item: dict[str, Any] | None) -> str:
    label = VENUE_LABELS[venue]
    if item is None:
        return '<div class="venue-cell"><div class="venue-price">—</div><div class="venue-gap incomplete">NO OBSERVATION</div></div>'
    if item["status"] in ("request_error", "api_error", "invalid_payload"):
        reason = item.get("error") or "Request did not return usable data"
        return (f'<div class="venue-cell"><div class="venue-price">—</div>'
                f'<div class="venue-gap incomplete">API / REQUEST ERROR</div>'
                f'<div class="venue-meta" title="{html.escape(reason, quote=True)}">{html.escape(label)} · inspect log</div></div>')
    if item["status"] == "incomplete_metrics":
        reason = item.get("error") or "Token metrics incomplete"
        return (f'<div class="venue-cell"><div class="venue-price">{_money(item["per_share_price"])}/share</div>'
                f'<div class="venue-gap incomplete">PRICE FIELD MISSING</div>'
                f'<div class="venue-meta" title="{html.escape(reason, quote=True)}">multiplier present · {html.escape(label)}</div></div>')
    if item["reference_state"] == "invalid":
        return (f'<div class="venue-cell"><div class="venue-price">{_money(item["per_share_price"])}/share</div>'
                f'<div class="venue-gap incomplete">INVALID REFERENCE</div>'
                f'<div class="venue-meta">source field not usable</div></div>')
    if item["spread_bps"] is None:
        return (f'<div class="venue-cell"><div class="venue-price">{_money(item["per_share_price"])}/share</div>'
                f'<div class="venue-gap missing">REFERENCE N/A</div>'
                f'<div class="venue-meta">source quote not returned</div></div>')
    gap = item["spread_bps"]
    css = "good" if abs(gap) < 5 else ("positive" if gap > 0 else "negative")
    return (f'<div class="venue-cell"><div class="venue-price">{_money(item["per_share_price"])}/share</div>'
            f'<div class="venue-gap {css}">{_bps(gap)}</div>'
            f'<div class="venue-meta">normalized · {_money(item["stock_price"])} source field</div></div>')


def _pairwise_cell(basis_bps: Any) -> str:
    if basis_bps is None:
        return ('<div class="pairwise-cell"><div class="venue-gap missing">PAIR N/A</div>'
                '<div class="venue-meta">both token prices required</div></div>')
    basis = _safe_float(basis_bps)
    if basis is None or not math.isfinite(basis):
        return '<div class="pairwise-cell"><div class="venue-gap missing">PAIR N/A</div><div class="venue-meta">invalid basis</div></div>'
    css = "good" if abs(basis) < 5 else ("positive" if basis > 0 else "negative")
    return (f'<div class="pairwise-cell"><div class="venue-gap {css}">{_bps(basis)}</div>'
            '<div class="venue-meta">bStocks vs Ondo · token-to-token</div></div>')


def _render_row(row: dict[str, Any]) -> str:
    ticker = html.escape(row["ticker"])
    quote_source = VENUE_LABELS.get(row["quote_source"], "")
    quote = _money(row["source_quote"])
    if row["source_quote"] is None:
        quote_detail = "not returned by available sources"
    else:
        quote_detail = f"reported via {quote_source} · independence unverified"
    state_class = row["integrity_class"]
    gap_attr = "1" if row["has_issue"] else "0"
    outlier_attr = "1" if state_class == "outlier" else "0"
    return (
        f'<tr class="data-row" data-ticker="{ticker}" data-outlier="{outlier_attr}" data-gap="{gap_attr}">'
        f'<td><div class="asset-name">{ticker}</div><div class="asset-contract">BSC · 3 listed forms</div></td>'
        f'<td><div class="reference-price">{quote}</div><div class="reference-source">{html.escape(quote_detail)}</div></td>'
        f'<td>{_venue_cell("ondo", row["venues"].get("ondo"))}</td>'
        f'<td>{_venue_cell("xstocks", row["venues"].get("xstocks"))}</td>'
        f'<td>{_venue_cell("bstocks", row["venues"].get("bstocks"))}</td>'
        f'<td>{_pairwise_cell(row.get("pairwise_basis_bps"))}</td>'
        f'<td><div class="quality {state_class}"><i class="quality-dot"></i><span class="quality-text">{html.escape(row["integrity_state"])}</span></div>'
        f'<div class="quality-note">{html.escape(row["integrity_note"])}</div></td></tr>'
    )


def _render_metric(label: str, value: str, foot: str, cls: str = "") -> str:
    return (f'<div class="metric {cls}"><div class="metric-label">{html.escape(label)}</div>'
            f'<div class="metric-value">{html.escape(value)}</div><div class="metric-foot">{html.escape(foot)}</div></div>')


def _render_pairwise_stats(summary: dict[str, Any]) -> str:
    pairs = int(summary.get("pair_count") or 0)
    universe = int(summary.get("universe_count") or 0)
    median_value = summary.get("median_bps")
    min_value = summary.get("min_bps")
    max_value = summary.get("max_bps")
    median_text = _bps(median_value) if median_value is not None else "—"
    if min_value is not None and max_value is not None:
        range_text = f"{_bps(min_value).removesuffix(' bp')} … {_bps(max_value)}"
    else:
        range_text = "—"
    cards = [
        ("Comparable pairs", f"{pairs} / {universe}", "valid normalized token prices", ""),
        ("Median signed basis", median_text, "positive = bStocks above Ondo", ""),
        ("Observed range", range_text, "latest completed poll", "range"),
        ("Absolute basis >100 bp", str(int(summary.get("over_100_bps") or 0)), "review only · not a trade trigger", ""),
    ]
    return "".join(
        f'<div class="basis-stat"><div class="basis-label">{html.escape(label)}</div>'
        f'<div class="basis-value {extra_class}">{html.escape(value)}</div>'
        f'<div class="basis-foot">{html.escape(foot)}</div></div>'
        for label, value, foot, extra_class in cards
    )


def _render_pairwise_top(rows: list[dict[str, Any]]) -> str:
    chips = []
    for row in rows[:3]:
        basis = _safe_float(row.get("basis_bps"))
        if basis is None:
            continue
        direction = "above" if basis > 0 else "below"
        chips.append(
            f'<span class="basis-chip {direction}">{html.escape(row["ticker"])} {_bps(basis)}</span>'
        )
    if not chips:
        chips = ['<span class="basis-chip">No comparable pairs in this poll</span>']
    return '<span class="basis-leaders-label">Largest |basis|</span>' + "".join(chips)


def _render_top_gaps(gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return '<div class="empty">No reference-quote gaps in the latest poll.</div>'
    cards = []
    for gap in gaps[:3]:
        val = gap["spread_bps"]
        css = "red" if abs(val) >= 1000 else "teal"
        cards.append(
            f'<div class="issue"><div class="issue-icon {css}">Δ</div><div>'
            f'<div class="issue-title">{html.escape(gap["ticker"])} · {html.escape(gap["venue_label"])} · {_bps(val)}</div>'
            f'<div class="issue-copy">{_money(gap["per_share_price"])}/share after normalization. Data discrepancy only; not an execution quote.</div>'
            f'</div></div>'
        )
    return "".join(cards)


def render_dashboard(snapshot: dict[str, Any], embedded_histories: dict[str, Any] | None = None,
                     static_preview: bool = False) -> str:
    poll = snapshot["poll"]
    completed = poll.get("completed_at_utc") or "—"
    expected = int(poll.get("expected_observations") or 0)
    responses = int(poll.get("response_rows") or 0)
    spreads = int(poll.get("spreads_computed") or 0)
    missing = int(poll.get("missing_references") or 0)
    incomplete = int(poll.get("incomplete_metrics") or 0)
    failures = int(poll.get("request_failures") or 0)
    metrics = "".join([
        _render_metric("Triple-listed tickers", str(snapshot["universe_count"]), "Ondo · xStocks · bStocks", "accent"),
        _render_metric("Reference-quote gaps", f"{spreads} / {expected}", "Per-share comparisons vs stockInfo.price", "accent"),
        _render_metric("Missing references", str(missing), "Responses with no source quote field", "warn"),
        _render_metric("Incomplete / API errors", f"{incomplete} / {failures}", "Missing token metrics / failed requests", "alert" if incomplete or failures else ""),
    ])
    rows_html = "".join(_render_row(row) for row in snapshot["tickers"])
    option_html = "".join(f'<option value="{html.escape(row["ticker"])}">{html.escape(row["ticker"])}</option>'
                           for row in sorted(snapshot["tickers"], key=lambda x: x["ticker"]))
    poll_duration = snapshot.get("poll_seconds")
    duration_text = f" · {poll_duration:.1f}s sweep" if poll_duration is not None else ""
    top_html = _render_top_gaps(snapshot["top_gaps"])
    pairwise_summary = snapshot.get("pairwise_basis", {})
    pairwise_stats_html = _render_pairwise_stats(pairwise_summary)
    pairwise_top_html = _render_pairwise_top(pairwise_summary.get("top", []))
    # The embedded data backs filters; static snapshots also carry history so they work offline.
    page_data: dict[str, Any] = {"tickers": [row["ticker"] for row in snapshot["tickers"]], "static_preview": static_preview}
    if embedded_histories is not None:
        page_data["histories"] = embedded_histories
    data_json = json.dumps(page_data, ensure_ascii=False)
    data_json = data_json.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    html_doc = HTML_TEMPLATE
    html_doc = html_doc.replace("__ASOF__", html.escape(completed))
    html_doc = html_doc.replace("__METRICS__", metrics)
    html_doc = html_doc.replace("__ROWS__", rows_html)
    html_doc = html_doc.replace("__OPTIONS__", option_html)
    html_doc = html_doc.replace("__TOP__", top_html)
    html_doc = html_doc.replace("__PAIRWISE_STATS__", pairwise_stats_html)
    html_doc = html_doc.replace("__PAIRWISE_TOP__", pairwise_top_html)
    html_doc = html_doc.replace("__JSON__", data_json)
    html_doc = html_doc.replace("__DURATION__", html.escape(duration_text))
    refresh_meta = "" if static_preview else '<meta http-equiv="refresh" content="60">'
    refresh_label = "OFFLINE SNAPSHOT · EMBEDDED HISTORY" if static_preview else "AUTO-REFRESH 60S"
    html_doc = html_doc.replace("__REFRESH_META__", refresh_meta)
    html_doc = html_doc.replace("__REFRESH_LABEL__", refresh_label)
    return html_doc


class DashboardHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB
    universe_path = DEFAULT_UNIVERSE

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path in ("/", "/index.html"):
                snapshot = latest_snapshot(self.db_path, self.universe_path)
                self._send(render_dashboard(snapshot).encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/snapshot":
                payload = latest_snapshot(self.db_path, self.universe_path)
                self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                ticker = (query.get("ticker") or [""])[0]
                payload = history_for_ticker(self.db_path, ticker)
                self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/api/live-rwa":
                query = parse_qs(parsed.query)
                ticker = (query.get("ticker") or [""])[0]
                try:
                    payload = live_rwa_snapshot(ticker)
                    self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                except RwaApiError as exc:
                    body = json.dumps({"error": exc.message, "code": exc.code}).encode("utf-8")
                    self._send(body, "application/json; charset=utf-8", exc.http_status)
                return
            if parsed.path == "/health":
                self._send(b'{"ok":true}', "application/json; charset=utf-8")
                return
            self._send(b"Not found", "text/plain; charset=utf-8", 404)
        except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
            message = str(exc)
            if parsed.path.startswith("/api/") or parsed.path == "/health":
                self._send(json.dumps({"error": message}).encode("utf-8"), "application/json; charset=utf-8", 503)
            else:
                body = ("<!doctype html><meta charset='utf-8'><title>Proof of Price</title>"
                        "<body style='background:#0a1011;color:#edf2ed;font:16px system-ui;padding:48px'>"
                        "<h1>Proof of Price is waiting for data</h1><p>" + html.escape(message) +
                        "</p><p>Run <code>python3 monitor.py --tickers AAPL</code> from bnb-monitor first.</p></body>").encode("utf-8")
                self._send(body, "text/html; charset=utf-8", 503)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the Proof of Price local dashboard")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default 0.0.0.0 for preview access)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    DashboardHandler.db_path = args.database
    DashboardHandler.universe_path = args.universe
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Proof of Price dashboard listening on http://{args.host}:{args.port}")
    print(f"SQLite source: {args.database}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nDashboard server stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
