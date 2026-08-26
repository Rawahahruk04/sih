/**
 * AIPI Navigation and App State Types (Locked Architecture)
 */

export type NavigationKey = 
  | 'overview' 
  | 'route-analytics' 
  | 'lead-time' 
  | 'validation' 
  | 'volatility' 
  | 'methodology' 
  | 'api-explorer';

export type NavigationCategory = 
  | 'Overview'
  | 'Market Intelligence' 
  | 'Quality & Validation' 
  | 'Governance' 
  | 'Developer';

export interface NavigationItem {
  id: NavigationKey;
  label: string;
  category: NavigationCategory;
  iconName: string;
  badge?: string;
  description: string;
}

export interface BreadcrumbItem {
  label: string;
  id?: NavigationKey;
  isCurrent?: boolean;
}
