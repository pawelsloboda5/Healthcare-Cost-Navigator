"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type ProviderCriteria = { state: string; city: string; drg_code: string; min_rating: string; max_cost: string; limit: string };

type ProviderSearchFormProps = {
  criteria: ProviderCriteria;
  onChange: (c: ProviderCriteria) => void;
  onSearchStates: (states: string[]) => void | Promise<void>;
  onClear: () => void;
  loading?: boolean;
  onCheapest470?: (state?: string) => void | Promise<void>;
  onHighestRated?: (state?: string, city?: string) => void | Promise<void>;
  onVolumeLeaders?: (drg: string) => void | Promise<void>;
};

export default function ProviderSearchForm({ criteria, onChange, onSearchStates, onClear, loading, onCheapest470, onHighestRated, onVolumeLeaders }: ProviderSearchFormProps) {
  function parseStates(value: string): string[] {
    return value
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter((s) => s.length === 2);
  }

  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        <Input placeholder="State (NY or NY,CA)" maxLength={50} value={criteria.state} onChange={(e) => onChange({ ...criteria, state: e.target.value })} />
        <Input placeholder="City (New York)" value={criteria.city} onChange={(e) => onChange({ ...criteria, city: e.target.value })} />
        <Input placeholder="DRG Code (470)" value={criteria.drg_code} onChange={(e) => onChange({ ...criteria, drg_code: e.target.value })} />
        <Input placeholder="Min Rating (8.0)" value={criteria.min_rating} onChange={(e) => onChange({ ...criteria, min_rating: e.target.value })} />
        <Input placeholder="Max Cost (100000)" value={criteria.max_cost} onChange={(e) => onChange({ ...criteria, max_cost: e.target.value })} />
        <Input placeholder="Limit (10)" value={criteria.limit} onChange={(e) => onChange({ ...criteria, limit: e.target.value })} />
      </div>
      <div className="flex flex-wrap gap-2 mt-1">
        <Button className="shrink-0" disabled={!!loading} onClick={() => onSearchStates(parseStates(criteria.state))}>Search Providers</Button>
        <Button className="shrink-0" variant="secondary" onClick={onClear}>Clear</Button>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => onCheapest470?.(parseStates(criteria.state)[0])}>Cheapest DRG 470</Button>
          <Button variant="outline" onClick={() => onHighestRated?.(parseStates(criteria.state)[0], criteria.city || undefined)}>Highest Rated</Button>
          <Button variant="outline" onClick={() => criteria.drg_code && onVolumeLeaders?.(criteria.drg_code)}>Volume Leaders</Button>
        </div>
      </div>
    </div>
  );
}


