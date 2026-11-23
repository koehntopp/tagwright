'use client'

import { useEffect, useRef, useState } from 'react'
import { Pencil, Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

/** A divider band of a track list (ADR 0081): the subtitle of the run of tracks below it, with a pen to change it.
 *  `disc` shows the "Disc N" chip (multi-disc albums); `inside` (a change of subtitle within a disc) indents it and
 *  `onRemove` adds the x.
 *  `editing` / `onEdit` / `onCancel` let the list own the edit state, so "+ divider here" can open an empty one. */
export function SubtitleDivider({ disc, inside, subtitle, count, editing, onEdit, onSet, onCancel, onRemove, placeholder = 'No subtitle', cols, keep, onKeep, was, differs, disabled }: {
	disc?: string
	inside?: boolean
	/** import dialogs: `keep` = "Keep mine" (nothing is written for the run), `was` = what the files have now */
	keep?: boolean
	onKeep?: (keep: boolean) => void
	was?: string
	differs?: boolean
	disabled?: boolean
	subtitle: string
	count: number
	editing: boolean
	onEdit: () => void
	onSet: (text: string) => void
	onCancel: () => void
	onRemove?: () => void
	placeholder?: string
	cols: number
}) {
	const [text, setText] = useState(subtitle)
	const ref = useRef<HTMLInputElement>(null)
	useEffect(() => { if (editing) { setText(subtitle); ref.current?.focus() } }, [editing]) // eslint-disable-line react-hooks/exhaustive-deps
	return (
		<tr>
			<td colSpan={cols} className="p-0 pt-2">
				<div className={`flex min-h-9 items-center gap-2 border-y px-2 py-1 ${keep || disabled ? 'border-slate-200 bg-slate-100' : 'border-sky-200 bg-sky-50'} ${disabled ? 'opacity-60' : ''} ${inside ? `ml-4 border-l-4 ${keep || disabled ? 'border-l-slate-300' : 'border-l-sky-300'}` : ''}`}>
					{disc && <span className="shrink-0 rounded-full bg-sky-900 px-2.5 py-0.5 text-[11px] font-medium text-white">Disc {disc}</span>}
					{editing ? (
						<form className="flex flex-1 items-center gap-1.5" onSubmit={e => { e.preventDefault(); onSet(text) }}>
							<Input ref={ref} className="h-7 flex-1 border-sky-400 bg-white text-sm" aria-label="Subtitle" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); onCancel() } }} />
							<Button type="submit" size="xs" className="bg-slate-800 text-white hover:bg-slate-700">Set</Button>
							<Button type="button" size="xs" variant="outline" onClick={onCancel}>Cancel</Button>
						</form>
					) : (
						<>
							{was === undefined ? (
								<div className="flex min-w-0 flex-1 items-center gap-2">
									<span className={`min-w-0 truncate text-sm ${subtitle ? 'text-sky-950' : 'italic text-slate-400'}`} title={subtitle}>{subtitle || placeholder}</span>
								</div>
							) : (
								// import dialogs (ADR 0106): what the release says, then what the files have now
								<div className="grid min-w-0 flex-1 grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 text-sm">
									<span className="text-xs text-slate-500">Release:</span>
									<span className="flex min-w-0 items-center gap-2">
										<span className={`min-w-0 truncate ${keep ? 'text-slate-400 line-through' : subtitle ? 'font-medium text-sky-950' : 'italic text-slate-500'}`} title={subtitle}>{subtitle || 'none'}</span>
										{differs && !disabled && <span className="shrink-0 rounded-full bg-yellow-100 px-2 text-[11px] text-yellow-800">differs</span>}
									</span>
									<span className="text-xs text-slate-500">Current subtitle:</span>
									<span className={`min-w-0 truncate ${was ? (keep ? 'font-medium text-sky-950' : 'text-slate-700') : 'italic text-slate-500'}`} title={was}>{was || 'none'}</span>
								</div>
							)}
							{onKeep && !disabled && (
								<div className="flex shrink-0 overflow-hidden rounded-full border border-slate-300 text-[11px]" role="group" aria-label="Which subtitle is written">
									<button type="button" aria-pressed={!keep} onClick={() => onKeep(false)} className={`px-2.5 py-0.5 ${!keep ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-white'}`}>Release</button>
									<button type="button" aria-pressed={!!keep} onClick={() => onKeep(true)} className={`px-2.5 py-0.5 ${keep ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-white'}`}>Keep mine</button>
								</div>
							)}
							<span className="shrink-0 text-xs text-slate-500">{count} {count === 1 ? 'file' : 'files'}</span>
							{!disabled && <button type="button" className="shrink-0 rounded-full p-1 text-slate-600 hover:bg-white" title="Edit the subtitle" aria-label="Edit the subtitle" onClick={onEdit}><Pencil className="size-3" /></button>}
							{onRemove && !disabled && <button type="button" className="shrink-0 rounded-full p-1 text-slate-400 hover:bg-white hover:text-slate-700" title="Remove this divider" aria-label="Remove this divider" onClick={onRemove}><X className="size-3" /></button>}
						</>
					)}
				</div>
			</td>
		</tr>
	)
}

/** The gap between two tracks: a dashed line and "+ divider here" while the pointer is near or the button has focus. */
export function DividerGap({ onAdd, cols }: { onAdd: () => void; cols: number }) {
	return (
		<tr className="group/gap">
			<td colSpan={cols} className="relative h-1 p-0">
				<button type="button" onClick={onAdd} aria-label="Add a divider here" className="absolute inset-x-0 -top-2 z-10 flex h-5 items-center justify-center opacity-0 transition focus-visible:opacity-100 group-hover/gap:opacity-100">
					<span className="absolute inset-x-1 top-1/2 border-t border-dashed border-sky-300" />
					<span className="relative flex items-center gap-1 bg-white px-2 text-[11px] text-sky-700"><Plus className="size-3" />divider here</span>
				</button>
			</td>
		</tr>
	)
}
