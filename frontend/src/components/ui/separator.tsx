"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { SEPARATOR } from "@/components/ui/classes"
import { Separator as SeparatorPrimitive } from "radix-ui"

function Separator({
  className,
  orientation = "horizontal",
  decorative = true,
  ...props
}: React.ComponentProps<typeof SeparatorPrimitive.Root>) {
  return (
    <SeparatorPrimitive.Root
      data-slot="separator"
      decorative={decorative}
      orientation={orientation}
      className={cn(
        SEPARATOR,
        className
      )}
      {...props}
    />
  )
}

export { Separator }
