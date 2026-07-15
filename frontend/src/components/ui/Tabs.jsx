import * as RadixTabs from '@radix-ui/react-tabs'
import { forwardRef } from 'react'
import './ui.css'

/**
 * Radix-backed tabs primitive (E3-5).
 */
export const Tabs = RadixTabs.Root

export const TabsList = forwardRef(function TabsList({ className = '', ...props }, ref) {
  return (
    <RadixTabs.List
      ref={ref}
      className={['ui-tabs-list', className].filter(Boolean).join(' ')}
      {...props}
    />
  )
})

export const TabsTrigger = forwardRef(function TabsTrigger({ className = '', ...props }, ref) {
  return (
    <RadixTabs.Trigger
      ref={ref}
      className={['ui-tabs-trigger', className].filter(Boolean).join(' ')}
      {...props}
    />
  )
})

export const TabsContent = forwardRef(function TabsContent({ className = '', ...props }, ref) {
  return (
    <RadixTabs.Content
      ref={ref}
      className={['ui-tabs-content', className].filter(Boolean).join(' ')}
      {...props}
    />
  )
})

export default Tabs
