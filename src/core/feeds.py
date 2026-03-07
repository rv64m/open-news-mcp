from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .source_proxy import rss_proxy_url


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    category: str
    tier: int = 3
    tags: tuple[str, ...] = field(default_factory=tuple)
    lang: str | None = None


def _source(
    name: str,
    feed_url: str,
    *,
    category: str,
    tier: int,
    tags: Sequence[str] = (),
    lang: str | None = None,
) -> Source:
    return Source(
        name=name,
        url=rss_proxy_url(feed_url),
        category=category,
        tier=tier,
        tags=tuple(tags),
        lang=lang,
    )


SOURCE_GROUPS: dict[str, tuple[Source, ...]] = {
    "markets": (
        _source("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html", category="markets", tier=1, tags=("equities", "macro")),
        _source("MarketWatch", "https://news.google.com/rss/search?q=site:marketwatch.com+markets+when:1d&hl=en-US&gl=US&ceid=US:en", category="markets", tier=2, tags=("equities", "markets")),
        _source("Yahoo Finance", "https://finance.yahoo.com/rss/topstories", category="markets", tier=2, tags=("markets", "broad-market")),
        _source("Seeking Alpha", "https://seekingalpha.com/market_currents.xml", category="markets", tier=2, tags=("equities", "analysis")),
        _source("Reuters Markets", "https://news.google.com/rss/search?q=site:reuters.com+markets+stocks+when:1d&hl=en-US&gl=US&ceid=US:en", category="markets", tier=1, tags=("markets", "wire")),
        _source("Bloomberg Markets", "https://news.google.com/rss/search?q=site:bloomberg.com+markets+when:1d&hl=en-US&gl=US&ceid=US:en", category="markets", tier=1, tags=("markets", "terminal")),
        _source("Investing.com News", "https://news.google.com/rss/search?q=site:investing.com+markets+when:1d&hl=en-US&gl=US&ceid=US:en", category="markets", tier=3, tags=("markets", "retail")),
    ),
    "forex": (
        _source("Forex News", 'https://news.google.com/rss/search?q=("forex"+OR+"currency"+OR+"FX+market")+trading+when:1d&hl=en-US&gl=US&ceid=US:en', category="forex", tier=3, tags=("fx", "currencies")),
        _source("Dollar Watch", 'https://news.google.com/rss/search?q=("dollar+index"+OR+DXY+OR+"US+dollar"+OR+"euro+dollar")+when:2d&hl=en-US&gl=US&ceid=US:en', category="forex", tier=2, tags=("fx", "dxy", "usd")),
        _source("Central Bank Rates", 'https://news.google.com/rss/search?q=("central+bank"+OR+"interest+rate"+OR+"rate+decision"+OR+"monetary+policy")+when:2d&hl=en-US&gl=US&ceid=US:en', category="forex", tier=2, tags=("rates", "fx", "policy")),
    ),
    "bonds": (
        _source("Bond Market", 'https://news.google.com/rss/search?q=("bond+market"+OR+"treasury+yields"+OR+"bond+yields"+OR+"fixed+income")+when:2d&hl=en-US&gl=US&ceid=US:en', category="bonds", tier=2, tags=("fixed-income", "yields")),
        _source("Treasury Watch", 'https://news.google.com/rss/search?q=("US+Treasury"+OR+"Treasury+auction"+OR+"10-year+yield"+OR+"2-year+yield")+when:2d&hl=en-US&gl=US&ceid=US:en', category="bonds", tier=2, tags=("treasury", "yields")),
        _source("Corporate Bonds", 'https://news.google.com/rss/search?q=("corporate+bond"+OR+"high+yield"+OR+"investment+grade"+OR+"credit+spread")+when:3d&hl=en-US&gl=US&ceid=US:en', category="bonds", tier=3, tags=("credit", "spreads")),
    ),
    "commodities": (
        _source("Oil & Gas", 'https://news.google.com/rss/search?q=(oil+price+OR+OPEC+OR+"natural+gas"+OR+"crude+oil"+OR+WTI+OR+Brent)+when:1d&hl=en-US&gl=US&ceid=US:en', category="commodities", tier=2, tags=("oil", "gas", "energy")),
        _source("Gold & Metals", 'https://news.google.com/rss/search?q=(gold+price+OR+silver+price+OR+copper+OR+platinum+OR+"precious+metals")+when:2d&hl=en-US&gl=US&ceid=US:en', category="commodities", tier=2, tags=("gold", "silver", "metals")),
        _source("Agriculture", 'https://news.google.com/rss/search?q=(wheat+OR+corn+OR+soybeans+OR+coffee+OR+sugar)+price+OR+commodity+when:3d&hl=en-US&gl=US&ceid=US:en', category="commodities", tier=3, tags=("agriculture", "softs")),
        _source("Commodity Trading", 'https://news.google.com/rss/search?q=("commodity+trading"+OR+"futures+market"+OR+CME+OR+NYMEX+OR+COMEX)+when:2d&hl=en-US&gl=US&ceid=US:en', category="commodities", tier=3, tags=("futures", "commodities")),
    ),
    "crypto": (
        _source("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", category="crypto", tier=1, tags=("btc", "eth", "markets", "institutional")),
        _source("Cointelegraph", "https://cointelegraph.com/rss", category="crypto", tier=2, tags=("btc", "eth", "defi", "web3")),
        _source("The Block", "https://news.google.com/rss/search?q=site:theblock.co+when:1d&hl=en-US&gl=US&ceid=US:en", category="crypto", tier=2, tags=("markets", "policy", "institutional")),
        _source("BWEnews", "https://rss-public.bwe-ws.com", category="crypto", tier=3, tags=("alpha", "breaking", "chinese")),
        _source("Crypto News", 'https://news.google.com/rss/search?q=(bitcoin+OR+ethereum+OR+crypto+OR+"digital+assets")+when:1d&hl=en-US&gl=US&ceid=US:en', category="crypto", tier=3, tags=("btc", "eth", "altcoins")),
        _source("DeFi News", 'https://news.google.com/rss/search?q=(DeFi+OR+"decentralized+finance"+OR+DEX+OR+"yield+farming")+when:3d&hl=en-US&gl=US&ceid=US:en', category="crypto", tier=3, tags=("defi", "dex", "stablecoin")),
    ),
    "centralbanks": (
        _source("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", category="centralbanks", tier=1, tags=("rates", "liquidity", "fed")),
        _source("ECB Watch", 'https://news.google.com/rss/search?q=("European+Central+Bank"+OR+ECB+OR+Lagarde)+monetary+policy+when:3d&hl=en-US&gl=US&ceid=US:en', category="centralbanks", tier=2, tags=("ecb", "rates")),
        _source("BoJ Watch", 'https://news.google.com/rss/search?q=("Bank+of+Japan"+OR+BoJ)+monetary+policy+when:3d&hl=en-US&gl=US&ceid=US:en', category="centralbanks", tier=2, tags=("boj", "rates")),
        _source("BoE Watch", 'https://news.google.com/rss/search?q=("Bank+of+England"+OR+BoE)+monetary+policy+when:3d&hl=en-US&gl=US&ceid=US:en', category="centralbanks", tier=2, tags=("boe", "rates")),
        _source("PBoC Watch", 'https://news.google.com/rss/search?q=("People%27s+Bank+of+China"+OR+PBoC+OR+PBOC)+when:7d&hl=en-US&gl=US&ceid=US:en', category="centralbanks", tier=2, tags=("pboc", "china", "rates")),
        _source("Global Central Banks", 'https://news.google.com/rss/search?q=("rate+hike"+OR+"rate+cut"+OR+"interest+rate+decision")+central+bank+when:3d&hl=en-US&gl=US&ceid=US:en', category="centralbanks", tier=3, tags=("rates", "policy")),
    ),
    "economic": (
        _source("Economic Data", 'https://news.google.com/rss/search?q=(CPI+OR+inflation+OR+GDP+OR+"jobs+report"+OR+"nonfarm+payrolls"+OR+PMI)+when:2d&hl=en-US&gl=US&ceid=US:en', category="economic", tier=2, tags=("cpi", "inflation", "gdp", "nfp")),
        _source("Trade & Tariffs", 'https://news.google.com/rss/search?q=(tariff+OR+"trade+war"+OR+"trade+deficit"+OR+sanctions)+when:2d&hl=en-US&gl=US&ceid=US:en', category="economic", tier=2, tags=("trade", "tariffs")),
        _source("Housing Market", 'https://news.google.com/rss/search?q=("housing+market"+OR+"home+prices"+OR+"mortgage+rates"+OR+REIT)+when:3d&hl=en-US&gl=US&ceid=US:en', category="economic", tier=3, tags=("housing", "rates")),
    ),
    "ipo": (
        _source("IPO News", 'https://news.google.com/rss/search?q=(IPO+OR+"initial+public+offering"+OR+SPAC+OR+"direct+listing")+when:3d&hl=en-US&gl=US&ceid=US:en', category="ipo", tier=2, tags=("ipo", "equities")),
        _source("Earnings Reports", 'https://news.google.com/rss/search?q=("earnings+report"+OR+"quarterly+earnings"+OR+"revenue+beat"+OR+"earnings+miss")+when:2d&hl=en-US&gl=US&ceid=US:en', category="ipo", tier=2, tags=("earnings", "equities")),
        _source("M&A News", 'https://news.google.com/rss/search?q=("merger"+OR+"acquisition"+OR+"takeover+bid"+OR+"buyout")+billion+when:3d&hl=en-US&gl=US&ceid=US:en', category="ipo", tier=2, tags=("mna", "deals")),
    ),
    "derivatives": (
        _source("Options Market", 'https://news.google.com/rss/search?q=("options+market"+OR+"options+trading"+OR+"put+call+ratio"+OR+VIX)+when:2d&hl=en-US&gl=US&ceid=US:en', category="derivatives", tier=2, tags=("options", "vix")),
        _source("Futures Trading", 'https://news.google.com/rss/search?q=("futures+trading"+OR+"S%26P+500+futures"+OR+"Nasdaq+futures")+when:1d&hl=en-US&gl=US&ceid=US:en', category="derivatives", tier=2, tags=("futures", "equities")),
    ),
    "fintech": (
        _source("Fintech News", 'https://news.google.com/rss/search?q=(fintech+OR+"payment+technology"+OR+"neobank"+OR+"digital+banking")+when:3d&hl=en-US&gl=US&ceid=US:en', category="fintech", tier=3, tags=("fintech", "payments")),
        _source("Trading Tech", 'https://news.google.com/rss/search?q=("algorithmic+trading"+OR+"trading+platform"+OR+"quantitative+finance")+when:7d&hl=en-US&gl=US&ceid=US:en', category="fintech", tier=3, tags=("trading-tech", "quant")),
        _source("Blockchain Finance", 'https://news.google.com/rss/search?q=("blockchain+finance"+OR+"tokenization"+OR+"digital+securities"+OR+CBDC)+when:7d&hl=en-US&gl=US&ceid=US:en', category="fintech", tier=3, tags=("tokenization", "cbdc")),
    ),
    "regulation": (
        _source("SEC", "https://www.sec.gov/news/pressreleases.rss", category="regulation", tier=1, tags=("sec", "enforcement", "etf")),
        _source("Financial Regulation", "https://news.google.com/rss/search?q=(SEC+OR+CFTC+OR+FINRA+OR+FCA)+regulation+OR+enforcement+when:3d&hl=en-US&gl=US&ceid=US:en", category="regulation", tier=2, tags=("cftc", "fca", "finra", "enforcement")),
        _source("Banking Rules", 'https://news.google.com/rss/search?q=(Basel+OR+"capital+requirements"+OR+"banking+regulation")+when:7d&hl=en-US&gl=US&ceid=US:en', category="regulation", tier=2, tags=("banking", "basel")),
        _source("Crypto Regulation", 'https://news.google.com/rss/search?q=(crypto+regulation+OR+"digital+asset"+regulation+OR+"stablecoin"+regulation)+when:7d&hl=en-US&gl=US&ceid=US:en', category="regulation", tier=2, tags=("regulation", "stablecoin", "policy")),
    ),
    "institutional": (
        _source("Hedge Fund News", 'https://news.google.com/rss/search?q=("hedge+fund"+OR+"Bridgewater"+OR+"Citadel"+OR+"Renaissance")+when:7d&hl=en-US&gl=US&ceid=US:en', category="institutional", tier=3, tags=("hedge-fund", "institutional")),
        _source("Private Equity", 'https://news.google.com/rss/search?q=("private+equity"+OR+Blackstone+OR+KKR+OR+Apollo+OR+Carlyle)+when:3d&hl=en-US&gl=US&ceid=US:en', category="institutional", tier=3, tags=("private-equity", "deals")),
        _source("Sovereign Wealth", 'https://news.google.com/rss/search?q=("sovereign+wealth+fund"+OR+"pension+fund"+OR+"institutional+investor")+when:7d&hl=en-US&gl=US&ceid=US:en', category="institutional", tier=3, tags=("swf", "pension")),
    ),
    "analysis": (
        _source("Market Outlook", 'https://news.google.com/rss/search?q=("market+outlook"+OR+"stock+market+forecast"+OR+"bull+market"+OR+"bear+market")+when:3d&hl=en-US&gl=US&ceid=US:en', category="analysis", tier=3, tags=("outlook", "markets")),
        _source("Risk & Volatility", 'https://news.google.com/rss/search?q=(VIX+OR+"market+volatility"+OR+"risk+off"+OR+"market+correction")+when:3d&hl=en-US&gl=US&ceid=US:en', category="analysis", tier=3, tags=("risk", "volatility", "macro")),
        _source("Bank Research", 'https://news.google.com/rss/search?q=("Goldman+Sachs"+OR+"JPMorgan"+OR+"Morgan+Stanley")+forecast+OR+outlook+when:3d&hl=en-US&gl=US&ceid=US:en', category="analysis", tier=2, tags=("sell-side", "research")),
    ),
    "gccNews": (
        _source("Arabian Business", 'https://news.google.com/rss/search?q=site:arabianbusiness.com+(Saudi+Arabia+OR+UAE+OR+GCC)+when:7d&hl=en-US&gl=US&ceid=US:en', category="gccNews", tier=3, tags=("gcc", "mena")),
        _source("The National", 'https://news.google.com/rss/search?q=site:thenationalnews.com+(Abu+Dhabi+OR+UAE+OR+Saudi)+when:7d&hl=en-US&gl=US&ceid=US:en', category="gccNews", tier=2, tags=("gcc", "uae")),
        _source("Arab News", 'https://news.google.com/rss/search?q=site:arabnews.com+(Saudi+Arabia+OR+investment+OR+infrastructure)+when:7d&hl=en-US&gl=US&ceid=US:en', category="gccNews", tier=2, tags=("gcc", "saudi")),
        _source("Gulf FDI", 'https://news.google.com/rss/search?q=(PIF+OR+"DP+World"+OR+Mubadala+OR+ADNOC+OR+Masdar+OR+"ACWA+Power")+infrastructure+when:7d&hl=en-US&gl=US&ceid=US:en', category="gccNews", tier=3, tags=("gcc", "fdi")),
        _source("Gulf Investments", 'https://news.google.com/rss/search?q=("Saudi+Arabia"+OR+"UAE"+OR+"Abu+Dhabi")+investment+infrastructure+when:7d&hl=en-US&gl=US&ceid=US:en', category="gccNews", tier=3, tags=("gcc", "investments")),
        _source("Vision 2030", 'https://news.google.com/rss/search?q="Vision+2030"+(project+OR+investment+OR+announced)+when:14d&hl=en-US&gl=US&ceid=US:en', category="gccNews", tier=3, tags=("saudi", "vision-2030")),
    ),
    "commodity-news": (
        _source("Kitco News", "https://www.kitco.com/rss/KitcoNews.xml", category="commodity-news", tier=2, tags=("metals", "kitco")),
        _source("Mining.com", "https://www.mining.com/feed/", category="commodity-news", tier=2, tags=("mining", "commodities")),
        _source("Bloomberg Commodities", 'https://news.google.com/rss/search?q=site:bloomberg.com+commodities+OR+metals+OR+mining+when:1d&hl=en-US&gl=US&ceid=US:en', category="commodity-news", tier=1, tags=("commodities", "wire")),
        _source("Reuters Commodities", 'https://news.google.com/rss/search?q=site:reuters.com+commodities+OR+metals+OR+mining+when:1d&hl=en-US&gl=US&ceid=US:en', category="commodity-news", tier=1, tags=("commodities", "wire")),
        _source("S&P Global Commodity", 'https://news.google.com/rss/search?q=site:spglobal.com+commodities+metals+when:3d&hl=en-US&gl=US&ceid=US:en', category="commodity-news", tier=2, tags=("commodities", "spglobal")),
        _source("Commodity Trade Mantra", "https://www.commoditytrademantra.com/feed/", category="commodity-news", tier=3, tags=("commodities", "trading")),
        _source("CNBC Commodities", 'https://news.google.com/rss/search?q=site:cnbc.com+(commodities+OR+metals+OR+gold+OR+copper)+when:1d&hl=en-US&gl=US&ceid=US:en', category="commodity-news", tier=2, tags=("commodities", "tv")),
    ),
    "gold-silver": (
        _source("Kitco Gold", "https://www.kitco.com/rss/KitcoGold.xml", category="gold-silver", tier=2, tags=("gold", "kitco")),
        _source("Gold Price News", 'https://news.google.com/rss/search?q=(gold+price+OR+"gold+market"+OR+bullion+OR+LBMA)+when:1d&hl=en-US&gl=US&ceid=US:en', category="gold-silver", tier=2, tags=("gold", "bullion")),
        _source("Silver Price News", 'https://news.google.com/rss/search?q=(silver+price+OR+"silver+market"+OR+"silver+futures")+when:2d&hl=en-US&gl=US&ceid=US:en', category="gold-silver", tier=3, tags=("silver", "futures")),
        _source("Precious Metals", 'https://news.google.com/rss/search?q=("precious+metals"+OR+platinum+OR+palladium+OR+"gold+ETF"+OR+GLD+OR+SLV)+when:2d&hl=en-US&gl=US&ceid=US:en', category="gold-silver", tier=2, tags=("precious-metals", "etf")),
        _source("World Gold Council", 'https://news.google.com/rss/search?q="World+Gold+Council"+OR+"central+bank+gold"+OR+"gold+reserves"+when:7d&hl=en-US&gl=US&ceid=US:en', category="gold-silver", tier=2, tags=("gold", "reserves")),
        _source("GoldSeek", "https://news.goldseek.com/GoldSeek/rss.xml", category="gold-silver", tier=3, tags=("gold", "commentary")),
        _source("SilverSeek", "https://news.silverseek.com/SilverSeek/rss.xml", category="gold-silver", tier=3, tags=("silver", "commentary")),
    ),
    "energy": (
        _source("OilPrice.com", "https://oilprice.com/rss/main", category="energy", tier=2, tags=("oil", "energy")),
        _source("Rigzone", "https://www.rigzone.com/news/rss/rigzone_latest.aspx", category="energy", tier=2, tags=("oil", "upstream")),
        _source("EIA Reports", "https://www.eia.gov/rss/press_room.xml", category="energy", tier=1, tags=("eia", "inventory")),
        _source("OPEC News", 'https://news.google.com/rss/search?q=(OPEC+OR+"oil+price"+OR+"crude+oil"+OR+WTI+OR+Brent+OR+"oil+production")+when:1d&hl=en-US&gl=US&ceid=US:en', category="energy", tier=2, tags=("opec", "oil")),
        _source("Natural Gas News", 'https://news.google.com/rss/search?q=("natural+gas"+OR+LNG+OR+"gas+price"+OR+"Henry+Hub")+when:1d&hl=en-US&gl=US&ceid=US:en', category="energy", tier=2, tags=("gas", "lng")),
        _source("Energy Intel", 'https://news.google.com/rss/search?q=(energy+commodities+OR+"energy+market"+OR+"energy+prices")+when:2d&hl=en-US&gl=US&ceid=US:en', category="energy", tier=3, tags=("energy", "macro")),
        _source("Reuters Energy", 'https://news.google.com/rss/search?q=site:reuters.com+(oil+OR+gas+OR+energy)+when:1d&hl=en-US&gl=US&ceid=US:en', category="energy", tier=1, tags=("energy", "wire")),
    ),
    "mining-news": (
        _source("Mining Journal", "https://www.mining-journal.com/feed/", category="mining-news", tier=2, tags=("mining", "journal")),
        _source("Northern Miner", "https://www.northernminer.com/feed/", category="mining-news", tier=2, tags=("mining", "north-america")),
        _source("Mining Weekly", "https://www.miningweekly.com/rss/", category="mining-news", tier=2, tags=("mining", "weekly")),
        _source("Mining Technology", "https://www.mining-technology.com/feed/", category="mining-news", tier=2, tags=("mining", "technology")),
        _source("Australian Mining", "https://www.australianmining.com.au/feed/", category="mining-news", tier=2, tags=("mining", "australia")),
        _source("Mine Web (SNL)", 'https://news.google.com/rss/search?q=("mining+company"+OR+"mine+production"+OR+"mining+operations")+when:2d&hl=en-US&gl=US&ceid=US:en', category="mining-news", tier=3, tags=("mining", "operations")),
        _source("Resource World", 'https://news.google.com/rss/search?q=("mining+project"+OR+"mineral+exploration"+OR+"mine+development")+when:3d&hl=en-US&gl=US&ceid=US:en', category="mining-news", tier=3, tags=("mining", "exploration")),
    ),
    "critical-minerals": (
        _source("Benchmark Mineral", 'https://news.google.com/rss/search?q=("critical+minerals"+OR+"battery+metals"+OR+lithium+OR+cobalt+OR+"rare+earths")+when:2d&hl=en-US&gl=US&ceid=US:en', category="critical-minerals", tier=2, tags=("critical-minerals", "battery-metals")),
        _source("Lithium Market", 'https://news.google.com/rss/search?q=(lithium+price+OR+"lithium+market"+OR+"lithium+supply"+OR+spodumene+OR+LCE)+when:2d&hl=en-US&gl=US&ceid=US:en', category="critical-minerals", tier=2, tags=("lithium", "battery-metals")),
        _source("Cobalt Market", 'https://news.google.com/rss/search?q=(cobalt+price+OR+"cobalt+market"+OR+"DRC+cobalt"+OR+"battery+cobalt")+when:3d&hl=en-US&gl=US&ceid=US:en', category="critical-minerals", tier=3, tags=("cobalt", "battery-metals")),
        _source("Rare Earths News", 'https://news.google.com/rss/search?q=("rare+earth"+OR+"rare+earths"+OR+"REE"+OR+neodymium+OR+praseodymium)+when:3d&hl=en-US&gl=US&ceid=US:en', category="critical-minerals", tier=2, tags=("rare-earths", "ree")),
        _source("EV Battery Supply", 'https://news.google.com/rss/search?q=("EV+battery"+OR+"battery+supply+chain"+OR+"battery+materials")+when:3d&hl=en-US&gl=US&ceid=US:en', category="critical-minerals", tier=3, tags=("battery", "supply-chain")),
        _source("IEA Critical Minerals", 'https://news.google.com/rss/search?q=site:iea.org+(minerals+OR+critical+OR+battery)+when:14d&hl=en-US&gl=US&ceid=US:en', category="critical-minerals", tier=2, tags=("iea", "critical-minerals")),
        _source("Uranium Market", 'https://news.google.com/rss/search?q=(uranium+price+OR+"uranium+market"+OR+U3O8+OR+nuclear+fuel)+when:3d&hl=en-US&gl=US&ceid=US:en', category="critical-minerals", tier=2, tags=("uranium", "nuclear")),
    ),
    "base-metals": (
        _source("LME Metals", 'https://news.google.com/rss/search?q=(LME+OR+"London+Metal+Exchange")+copper+OR+aluminum+OR+zinc+OR+nickel+when:2d&hl=en-US&gl=US&ceid=US:en', category="base-metals", tier=2, tags=("lme", "metals")),
        _source("Copper Market", 'https://news.google.com/rss/search?q=(copper+price+OR+"copper+market"+OR+"copper+supply"+OR+COMEX+copper)+when:2d&hl=en-US&gl=US&ceid=US:en', category="base-metals", tier=2, tags=("copper", "comex")),
        _source("Nickel News", 'https://news.google.com/rss/search?q=(nickel+price+OR+"nickel+market"+OR+"nickel+supply"+OR+Indonesia+nickel)+when:3d&hl=en-US&gl=US&ceid=US:en', category="base-metals", tier=2, tags=("nickel", "indonesia")),
        _source("Aluminum & Zinc", 'https://news.google.com/rss/search?q=(aluminum+price+OR+aluminium+OR+zinc+price+OR+"base+metals")+when:3d&hl=en-US&gl=US&ceid=US:en', category="base-metals", tier=3, tags=("aluminum", "zinc")),
        _source("Iron Ore Market", 'https://news.google.com/rss/search?q=("iron+ore"+price+OR+"iron+ore+market"+OR+"steel+raw+materials")+when:2d&hl=en-US&gl=US&ceid=US:en', category="base-metals", tier=2, tags=("iron-ore", "steel")),
        _source("Metals Bulletin", 'https://news.google.com/rss/search?q=("metals+market"+OR+"base+metals"+OR+SHFE+OR+"Shanghai+Futures")+when:2d&hl=en-US&gl=US&ceid=US:en', category="base-metals", tier=3, tags=("shfe", "metals")),
    ),
    "mining-companies": (
        _source("BHP News", 'https://news.google.com/rss/search?q=BHP+(mining+OR+production+OR+results+OR+copper+OR+"iron+ore")+when:7d&hl=en-US&gl=US&ceid=US:en', category="mining-companies", tier=3, tags=("bhp", "miners")),
        _source("Rio Tinto News", 'https://news.google.com/rss/search?q="Rio+Tinto"+(mining+OR+production+OR+results+OR+Pilbara)+when:7d&hl=en-US&gl=US&ceid=US:en', category="mining-companies", tier=3, tags=("rio-tinto", "miners")),
        _source("Glencore & Vale", 'https://news.google.com/rss/search?q=(Glencore+OR+Vale)+(mining+OR+production+OR+cobalt+OR+"iron+ore")+when:7d&hl=en-US&gl=US&ceid=US:en', category="mining-companies", tier=3, tags=("glencore", "vale")),
        _source("Gold Majors", 'https://news.google.com/rss/search?q=(Newmont+OR+Barrick+OR+AngloGold+OR+Agnico)+(gold+mine+OR+production+OR+results)+when:7d&hl=en-US&gl=US&ceid=US:en', category="mining-companies", tier=3, tags=("gold-miners", "majors")),
        _source("Freeport & Copper Miners", 'https://news.google.com/rss/search?q=(Freeport+McMoRan+OR+Southern+Copper+OR+Teck+OR+Antofagasta)+when:7d&hl=en-US&gl=US&ceid=US:en', category="mining-companies", tier=3, tags=("copper-miners", "freeport")),
        _source("Critical Mineral Companies", 'https://news.google.com/rss/search?q=(Albemarle+OR+SQM+OR+"MP+Materials"+OR+Lynas+OR+Cameco)+when:7d&hl=en-US&gl=US&ceid=US:en', category="mining-companies", tier=3, tags=("critical-minerals", "miners")),
    ),
    "supply-chain": (
        _source("Shipping & Freight", 'https://news.google.com/rss/search?q=("bulk+carrier"+OR+"dry+bulk"+OR+"commodity+shipping"+OR+"Port+Hedland"+OR+"Strait+of+Hormuz")+when:3d&hl=en-US&gl=US&ceid=US:en', category="supply-chain", tier=3, tags=("shipping", "freight")),
        _source("Trade Routes", 'https://news.google.com/rss/search?q=("trade+route"+OR+"supply+chain"+OR+"commodity+export"+OR+"mineral+export")+when:3d&hl=en-US&gl=US&ceid=US:en', category="supply-chain", tier=3, tags=("routes", "exports")),
        _source("China Commodity Imports", 'https://news.google.com/rss/search?q=(China+imports+copper+OR+iron+ore+OR+lithium+OR+cobalt+OR+"rare+earth")+when:3d&hl=en-US&gl=US&ceid=US:en', category="supply-chain", tier=3, tags=("china", "imports")),
        _source("Port & Logistics", 'https://news.google.com/rss/search?q=("iron+ore+port"+OR+"copper+port"+OR+"commodity+port"+OR+"mineral+logistics")+when:7d&hl=en-US&gl=US&ceid=US:en', category="supply-chain", tier=3, tags=("ports", "logistics")),
    ),
    "commodity-regulation": (
        _source("Mining Regulation", 'https://news.google.com/rss/search?q=("mining+regulation"+OR+"mining+policy"+OR+"mining+permit"+OR+"mining+ban")+when:7d&hl=en-US&gl=US&ceid=US:en', category="commodity-regulation", tier=3, tags=("mining", "policy")),
        _source("ESG in Mining", 'https://news.google.com/rss/search?q=("mining+ESG"+OR+"responsible+mining"+OR+"mine+closure"+OR+"tailings")+when:7d&hl=en-US&gl=US&ceid=US:en', category="commodity-regulation", tier=3, tags=("esg", "mining")),
        _source("Trade & Tariffs Minerals", 'https://news.google.com/rss/search?q=("mineral+tariff"+OR+"metals+tariff"+OR+"critical+mineral+policy"+OR+"mining+export+ban")+when:7d&hl=en-US&gl=US&ceid=US:en', category="commodity-regulation", tier=3, tags=("tariffs", "minerals")),
        _source("Indonesia Nickel Policy", 'https://news.google.com/rss/search?q=(Indonesia+nickel+OR+"nickel+export"+OR+"nickel+ban"+OR+"nickel+processing")+when:7d&hl=en-US&gl=US&ceid=US:en', category="commodity-regulation", tier=2, tags=("nickel", "indonesia")),
        _source("China Mineral Policy", 'https://news.google.com/rss/search?q=(China+"rare+earth"+OR+"mineral+export"+OR+"critical+mineral")+policy+OR+restriction+when:7d&hl=en-US&gl=US&ceid=US:en', category="commodity-regulation", tier=2, tags=("china", "minerals", "policy")),
    ),
    "macro": (),
}

SOURCE_GROUPS["macro"] = SOURCE_GROUPS["centralbanks"] + SOURCE_GROUPS["economic"] + SOURCE_GROUPS["analysis"]

_source_index: dict[str, Source] = {}
for group in SOURCE_GROUPS.values():
    for source in group:
        _source_index.setdefault(source.name, source)

ALL_SOURCES: tuple[Source, ...] = tuple(_source_index.values())

SOURCE_TIERS: dict[str, int] = {source.name: source.tier for source in ALL_SOURCES}


def get_source_tier(name: str, default: int = 4) -> int:
    return SOURCE_TIERS.get(name, default)


def get_sources(*, categories: Iterable[str] | None = None) -> list[Source]:
    if categories is None:
        return list(ALL_SOURCES)

    selected: list[Source] = []
    for category in categories:
        selected.extend(SOURCE_GROUPS.get(category, ()))
    return selected
