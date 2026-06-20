import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'border-aegis-accent/30 bg-aegis-accent/10 text-aegis-accent',
        secondary: 'border-aegis-border bg-aegis-border/50 text-aegis-text-dim',
        destructive: 'border-red-800/50 bg-red-950/40 text-aegis-critical',
        outline: 'border-aegis-border text-aegis-text-dim',
      },
    },
    defaultVariants: { variant: 'default' },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
