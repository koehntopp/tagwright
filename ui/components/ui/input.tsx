import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"
import { X } from "lucide-react"
import { cn } from "cn"

// ADR 0094: single-line text fields get an x that empties them; number, read-only and disabled fields do not.
const CLEARABLE = new Set(["text", "search", "password", "email", "url", "tel"])
// Layout classes size the wrapper (the field sits in rows and table cells); the rest style the input.
const LAYOUT = /^(?:w-|min-w-|max-w-|flex-|basis-|grow|shrink|self-)/

function Input({ className, type, ref, clearable: allowClear = true, ...props }: React.ComponentProps<"input"> & { clearable?: boolean }) {
  const inner = React.useRef<HTMLInputElement | null>(null)
  const [typed, setTyped] = React.useState(false)
  const clearable = allowClear && CLEARABLE.has(type ?? "text") && !props.readOnly && !props.disabled
  const setRef = (el: HTMLInputElement | null) => {
    inner.current = el
    if (typeof ref === "function") ref(el)
    else if (ref) ref.current = el
  }
  const classes = cn(
    "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
    clearable && "pr-7 [&::-webkit-search-cancel-button]:appearance-none",
    className
  )
  if (!clearable) return <InputPrimitive type={type} data-slot="input" ref={setRef} className={classes} {...props} />

  const tokens = (className ?? "").split(/\s+/).filter(Boolean)
  const outer = tokens.filter(t => LAYOUT.test(t)).join(" ")
  const field = cn(classes, "w-full")
  const filled = props.value !== undefined ? String(props.value) !== "" : typed
  const clear = () => {
    const el = inner.current
    if (!el) return
    // Through the native setter and an input event, so a controlled field's onChange sees it like typing.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(el, "")
    el.dispatchEvent(new Event("input", { bubbles: true }))
    setTyped(false)
    el.focus()
  }
  return (
    <span className={cn("group/clear relative inline-flex w-full min-w-0", outer)}>
      <InputPrimitive
        type={type}
        data-slot="input"
        ref={setRef}
        className={field}
        {...props}
        onInput={e => {
          setTyped(e.currentTarget.value !== "")
          props.onInput?.(e)
        }}
      />
      {filled && (
        <button
          type="button"
          tabIndex={-1}
          aria-label="Clear"
          title="Clear"
          onMouseDown={e => e.preventDefault()}
          onClick={clear}
          className="invisible absolute top-1/2 right-2 -translate-y-1/2 cursor-pointer rounded-full text-slate-400 group-focus-within/clear:visible group-hover/clear:visible hover:text-slate-700"
        >
          <X className="size-3.5" />
        </button>
      )}
    </span>
  )
}

export { Input }
