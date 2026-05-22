// Inline lucide-style icons. 24x24 viewbox, stroke = currentColor.
// Exposed on window so other babel scripts can use them.

const Icon = ({ children, size = 20, className = '', strokeWidth = 1.75, fill = 'none', ...rest }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={fill}
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...rest}
  >
    {children}
  </svg>
);

const Search       = (p) => <Icon {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Icon>;
const X            = (p) => <Icon {...p}><path d="M18 6 6 18M6 6l12 12" /></Icon>;
const Sun          = (p) => <Icon {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" /></Icon>;
const Moon         = (p) => <Icon {...p}><path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z" /></Icon>;
const ChevronDown  = (p) => <Icon {...p}><path d="m6 9 6 6 6-6" /></Icon>;
const ChevronUp    = (p) => <Icon {...p}><path d="m18 15-6-6-6 6" /></Icon>;
const ExternalLink = (p) => <Icon {...p}><path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" /></Icon>;
const ImageOff     = (p) => <Icon {...p}><path d="m2 2 20 20" /><path d="M10.41 10.41a2 2 0 1 1-2.83-2.83" /><path d="M13.5 13.86 21 21" /><path d="M18 12V5a2 2 0 0 0-2-2H7" /><path d="M21 15V5" /><path d="M3.59 3.59A2 2 0 0 0 3 5v14a2 2 0 0 0 2 2h14c.55 0 1.05-.22 1.41-.59" /><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L13 14" /></Icon>;
const SlidersH     = (p) => <Icon {...p}><line x1="21" y1="6" x2="14" y2="6" /><line x1="10" y1="6" x2="3" y2="6" /><line x1="21" y1="12" x2="16" y2="12" /><line x1="12" y1="12" x2="3" y2="12" /><line x1="21" y1="18" x2="8" y2="18" /><line x1="4" y1="18" x2="3" y2="18" /><circle cx="12" cy="6" r="2" /><circle cx="14" cy="12" r="2" /><circle cx="6" cy="18" r="2" /></Icon>;
const Check        = (p) => <Icon {...p}><path d="M20 6 9 17l-5-5" /></Icon>;

// Star — fill follows `filled` flag
const Star = ({ filled = false, ...p }) => (
  <Icon {...p} fill={filled ? 'currentColor' : 'none'}>
    <path d="m12 17.27 6.18 3.73-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
  </Icon>
);

// Sparkle (used for Bat's List marker)
const Sparkle = (p) => (
  <Icon {...p}>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
  </Icon>
);

// Heart-outline (used for Bat's List tab indicator)
const Tag = (p) => (
  <Icon {...p}>
    <path d="M20 12V7a2 2 0 0 0-2-2h-5L3 15l6 6 10-10z" />
    <circle cx="14" cy="9" r="1.2" fill="currentColor" stroke="none" />
  </Icon>
);

// Day icons
const SunSmall  = Sun;
const MoonSmall = Moon;

Object.assign(window, {
  Icon, Search, X, Sun, Moon, ChevronDown, ChevronUp, ExternalLink,
  ImageOff, SlidersH, Check, Star, Sparkle, Tag, SunSmall, MoonSmall,
});
