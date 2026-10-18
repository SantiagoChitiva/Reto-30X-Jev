import { cn } from "@/lib/utils";

/** Logotipo "30X" como en 30x.com: cifras en blanco y la X en lima. */
export function Logo30X({ className }: { className?: string }) {
  return (
    <span
      aria-label="30X"
      className={cn("font-extrabold tracking-[-0.06em]", className)}
    >
      30<span className="text-brand-lime">X</span>
    </span>
  );
}
