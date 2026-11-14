import type { ButtonHTMLAttributes, ReactNode } from "react";

export type Variant = "glass" | "blue" | "magenta" | "aurora" | "ghost";
export type Size = "sm" | "md" | "lg";

const cls = (variant: Variant, size: Size, extra?: string) =>
  ["btn", variant !== "glass" && `btn-${variant}`, size !== "md" && `btn-${size}`, extra].filter(Boolean).join(" ");

export function Button({ variant = "glass", size = "md", loading = false, icon, children, className, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean; icon?: ReactNode }) {
  return (
    <button {...rest} className={cls(variant, size, className)} disabled={disabled || loading} aria-busy={loading || undefined}>
      {loading ? <span className="spinner" aria-hidden="true" /> : icon}
      {children}
    </button>
  );
}

/** A link styled as a button (for navigation and downloads). */
export function LinkButton({ variant = "glass", size = "md", icon, children, className, ...rest }:
  React.AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant; size?: Size; icon?: ReactNode }) {
  return <a {...rest} className={cls(variant, size, className)}>{icon}{children}</a>;
}
