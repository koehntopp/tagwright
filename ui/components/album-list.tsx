'use client'

import { Album, STATUS, coverUrl, title } from '@/lib/api'

// One line per album, the same order and colour meanings as the cards (ADR 0085).
const COLS = 'grid grid-cols-[2.25rem_minmax(9rem,1.2fr)_minmax(12rem,1.6fr)_4.5rem_minmax(7rem,1fr)_5.5rem_5.5rem] items-center gap-x-3'
const DOT = { needs: 'bg-rose-600', ready: 'bg-sky-600', fixed: 'bg-emerald-600' }

function MiniCover({ a }: { a: Album }) {
	const hue = [...(a.artist || a.name)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7)
	const initials = (a.artist || a.name || '?').split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()
	return (
		<div className="relative size-9 shrink-0 overflow-hidden rounded-md" style={{ background: `linear-gradient(135deg,hsl(${hue} 70% 62%),hsl(${(hue + 40) % 360} 60% 30%))` }}>
			<span className="absolute inset-0 grid place-items-center text-[11px] font-bold text-white/80">{initials}</span>
			{a.cover && (
				// eslint-disable-next-line @next/next/no-img-element
				<img src={coverUrl(a)} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" onError={e => e.currentTarget.remove()} />
			)}
			<span title={STATUS[a.status]} className={`absolute -right-0.5 -top-0.5 size-2 rounded-full ring-1 ring-white ${DOT[a.status]}`} />
		</div>
	)
}

export function AlbumList({ albums, selected, onSelect }: { albums: Album[]; selected: string | null; onSelect: (path: string) => void }) {
	return (
		<div className="overflow-hidden rounded-2xl border border-slate-200 bg-white/70">
			<div className={`${COLS} border-b border-slate-200 px-4 py-2 text-xs font-medium text-slate-500`}>
				<span />
				<span>Album artist</span>
				<span>Release name</span>
				<span>Media</span>
				<span>Edition</span>
				<span>Release year</span>
				<span>Master year</span>
			</div>
			{albums.map(a => (
				<div key={a.path} role="button" tabIndex={0} aria-label={`${a.artist || ''} - ${title(a)}`}
					onClick={() => onSelect(a.path)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(a.path) } }}
					className={`${COLS} cursor-pointer border-b border-slate-100 px-4 py-2 leading-tight last:border-b-0 hover:bg-slate-50 ${a.path === selected ? 'bg-slate-100' : ''}`}>
					<MiniCover a={a} />
					<span className="truncate" title={a.artist}>{a.artist || 'No artist'}</span>
					<span className="truncate font-medium" title={title(a)}>{title(a)}</span>
					<span className="truncate text-slate-600" title={a.media}>{a.media}</span>
					<span className="truncate text-slate-600" title={a.edition_name}>{a.edition_name}</span>
					<span className="tabular-nums text-slate-600">{a.release_year}</span>
					<span className="tabular-nums text-slate-600">{a.master_year}</span>
				</div>
			))}
		</div>
	)
}
