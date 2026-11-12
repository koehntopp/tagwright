// A flag for a release country: Discogs writes names ("UK", "Germany", "Europe"), MusicBrainz ISO codes ("DE", "XE").
const ALIAS: Record<string, string> = {
	uk: 'GB', 'uk & ireland': 'GB', 'uk & europe': 'GB', us: 'US', usa: 'US', 'us & canada': 'US', europe: 'EU', xe: 'EU',
	ussr: 'RU', russia: 'RU', 'czech republic': 'CZ', czechia: 'CZ', 'south korea': 'KR', korea: 'KR', taiwan: 'TW',
	'hong kong': 'HK', vietnam: 'VN', 'bosnia & herzegovina': 'BA', 'trinidad & tobago': 'TT', 'serbia & montenegro': 'RS',
	'east germany': 'DE', 'west germany': 'DE', 'germany, austria, & switzerland': 'DE', 'netherlands': 'NL',
}
let byName: Map<string, string> | null = null

function codeOf(country: string): string {
	const c = country.trim()
	if (!c) return ''
	const alias = ALIAS[c.toLowerCase()]
	if (alias) return alias
	if (/^[A-Za-z]{2}$/.test(c)) return c.toUpperCase()
	if (!byName) {
		byName = new Map()
		const names = new Intl.DisplayNames(['en'], { type: 'region' })
		for (let a = 65; a <= 90; a++) for (let b = 65; b <= 90; b++) {
			const code = String.fromCharCode(a, b)
			try { const n = names.of(code); if (n && n !== code) byName.set(n.toLowerCase(), code) } catch { /* not a region */ }
		}
	}
	return byName.get(c.toLowerCase()) ?? ''
}

/** The flag emoji of a country name or code, or '' when it has none (Worldwide, Scandinavia, ...). */
export function flagOf(country: string): string {
	const code = codeOf(country)
	return code.length === 2 ? String.fromCodePoint(...[...code].map(ch => 0x1f1a5 + ch.charCodeAt(0))) : ''
}
