import type { Vendor, VendorDraft } from './types'

export function vendorDraftFor(
  vendor: Vendor,
  drafts: Record<string, VendorDraft>,
): VendorDraft {
  return (
    drafts[vendor.id] ?? {
      vendor_name: vendor.vendor_name,
      contact: vendor.contact,
      quotation: vendor.quotation === null ? '' : String(vendor.quotation),
      status: vendor.status,
      notes: vendor.notes,
    }
  )
}

export function applyVendorDraft<Key extends keyof VendorDraft>(
  drafts: Record<string, VendorDraft>,
  vendor: Vendor,
  field: Key,
  value: VendorDraft[Key],
): Record<string, VendorDraft> {
  return {
    ...drafts,
    [vendor.id]: { ...vendorDraftFor(vendor, drafts), [field]: value },
  }
}
