/* @ds-bundle: {"format":4,"namespace":"OurHikeDesignSystem_60cee1","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Callout","sourcePath":"components/feedback/Callout.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Footer","sourcePath":"components/navigation/Footer.jsx"},{"name":"NavBar","sourcePath":"components/navigation/NavBar.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"3f2d51abc741","components/core/Button.jsx":"de80c74f463d","components/core/Card.jsx":"4f8336da505c","components/feedback/Callout.jsx":"8d4270c363a0","components/forms/Input.jsx":"74cdd823f23b","components/forms/Select.jsx":"dbb14bcf5105","components/navigation/Footer.jsx":"f05d07ce1b3f","components/navigation/NavBar.jsx":"72115879f347","ui_kits/website/Homepage.jsx":"d83f3fc8a4d2"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.OurHikeDesignSystem_60cee1 = window.OurHikeDesignSystem_60cee1 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
const tones = {
  easy: {
    bg: 'var(--sage-100)',
    fg: 'var(--forest-600)',
    border: 'var(--moss-300)'
  },
  moderate: {
    bg: '#fbeed9',
    fg: '#8a5a1a',
    border: 'var(--blaze-yellow)'
  },
  strenuous: {
    bg: '#f6e3cf',
    fg: 'var(--blaze-orange-dark)',
    border: 'var(--blaze-orange)'
  },
  info: {
    bg: '#dbe7ef',
    fg: 'var(--blaze-blue)',
    border: 'var(--blaze-blue)'
  },
  neutral: {
    bg: 'var(--stone-150)',
    fg: 'var(--stone-700)',
    border: 'var(--stone-300)'
  }
};
function Badge({
  children,
  tone = 'neutral'
}) {
  const t = tones[tone] || tones.neutral;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      padding: '4px 12px',
      borderRadius: 'var(--radius-pill)',
      background: t.bg,
      color: t.fg,
      border: `1px solid ${t.border}`,
      fontFamily: 'var(--font-body)',
      fontSize: 'var(--text-caption)',
      fontWeight: 'var(--weight-semibold)',
      letterSpacing: 'var(--tracking-wide)',
      textTransform: 'uppercase'
    }
  }, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
const sizes = {
  s: {
    padding: '8px 16px',
    fontSize: 'var(--text-body-s)'
  },
  m: {
    padding: '11px 22px',
    fontSize: 'var(--text-body)'
  },
  l: {
    padding: '14px 28px',
    fontSize: 'var(--text-body-l)'
  }
};
const variants = {
  primary: {
    background: 'var(--brand-primary)',
    color: 'var(--paper-0)',
    border: '1px solid var(--brand-primary)'
  },
  secondary: {
    background: 'var(--blaze-orange)',
    color: 'var(--paper-0)',
    border: '1px solid var(--blaze-orange)'
  },
  outline: {
    background: 'transparent',
    color: 'var(--brand-primary)',
    border: '1px solid var(--border-2)'
  },
  ghost: {
    background: 'transparent',
    color: 'var(--fg-2)',
    border: '1px solid transparent'
  }
};
function Button({
  children,
  variant = 'primary',
  size = 'm',
  disabled = false,
  onClick,
  style
}) {
  const v = variants[variant] || variants.primary;
  const s = sizes[size] || sizes.m;
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);
  let bg = v.background;
  if (!disabled && variant === 'primary') bg = active ? 'var(--brand-primary-press)' : hover ? 'var(--brand-primary-hover)' : v.background;
  if (!disabled && variant === 'secondary') bg = active || hover ? 'var(--brand-secondary-hover)' : v.background;
  if (!disabled && variant === 'outline') bg = hover ? 'var(--sage-100)' : v.background;
  if (!disabled && variant === 'ghost') bg = hover ? 'var(--sage-100)' : v.background;
  return /*#__PURE__*/React.createElement("button", {
    onClick: disabled ? undefined : onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setActive(false);
    },
    onMouseDown: () => setActive(true),
    onMouseUp: () => setActive(false),
    disabled: disabled,
    style: {
      fontFamily: 'var(--font-body)',
      fontWeight: 'var(--weight-semibold)',
      borderRadius: 'var(--radius-pill)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.45 : 1,
      transition: 'background var(--duration-fast) var(--ease-standard), transform var(--duration-fast) var(--ease-standard)',
      transform: active && !disabled ? 'scale(0.97)' : 'scale(1)',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      ...s,
      ...v,
      background: bg,
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function Card({
  image,
  eyebrow,
  title,
  meta,
  children,
  footer
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      borderRadius: 'var(--radius-l)',
      overflow: 'hidden',
      boxShadow: 'var(--shadow-card)',
      border: '1px solid var(--border-1)',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-body)'
    }
  }, image && /*#__PURE__*/React.createElement("div", {
    style: {
      height: 160,
      background: 'var(--sage-100)'
    }
  }, image), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 'var(--space-5)',
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--space-2)',
      flex: 1
    }
  }, eyebrow && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-eyebrow)',
      letterSpacing: 'var(--tracking-eyebrow)',
      textTransform: 'uppercase',
      color: 'var(--forest-600)',
      fontWeight: 'var(--weight-semibold)'
    }
  }, eyebrow), title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontSize: 'var(--text-heading)',
      color: 'var(--fg-1)',
      lineHeight: 'var(--leading-snug)'
    }
  }, title), meta && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-body-s)',
      color: 'var(--fg-3)'
    }
  }, meta), children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 'var(--space-4) var(--space-5)',
      borderTop: '1px solid var(--border-1)'
    }
  }, footer));
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Callout.jsx
try { (() => {
const tones = {
  brand: {
    bg: 'var(--sage-100)',
    border: 'var(--moss-300)',
    fg: 'var(--pine-800)'
  },
  urgent: {
    bg: '#f6e3cf',
    border: 'var(--blaze-orange)',
    fg: 'var(--blaze-orange-dark)'
  },
  info: {
    bg: '#dbe7ef',
    border: 'var(--blaze-blue)',
    fg: 'var(--pine-900)'
  }
};
function Callout({
  title,
  children,
  tone = 'brand',
  action
}) {
  const t = tones[tone] || tones.brand;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: t.bg,
      border: `1px solid ${t.border}`,
      borderRadius: 'var(--radius-m)',
      padding: 'var(--space-5)',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      fontFamily: 'var(--font-body)'
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 'var(--weight-semibold)',
      color: t.fg,
      fontSize: 'var(--text-body-l)'
    }
  }, title), children && /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--fg-2)',
      fontSize: 'var(--text-body)',
      lineHeight: 'var(--leading-normal)'
    }
  }, children), action);
}
Object.assign(__ds_scope, { Callout });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Callout.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function Input({
  label,
  placeholder,
  type = 'text',
  value,
  onChange,
  error
}) {
  const [focus, setFocus] = React.useState(false);
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      fontFamily: 'var(--font-body)'
    }
  }, label && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-body-s)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--fg-2)'
    }
  }, label), /*#__PURE__*/React.createElement("input", {
    type: type,
    placeholder: placeholder,
    value: value,
    onChange: onChange,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      padding: '11px 14px',
      borderRadius: 'var(--radius-m)',
      border: `1px solid ${error ? 'var(--danger)' : focus ? 'var(--brand-primary)' : 'var(--border-2)'}`,
      boxShadow: focus ? 'var(--shadow-focus)' : 'none',
      fontSize: 'var(--text-body)',
      color: 'var(--fg-1)',
      background: 'var(--white)',
      outline: 'none',
      transition: 'border var(--duration-fast), box-shadow var(--duration-fast)'
    }
  }), error && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-caption)',
      color: 'var(--danger)'
    }
  }, error));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function Select({
  label,
  options = [],
  value,
  onChange
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      fontFamily: 'var(--font-body)'
    }
  }, label && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-body-s)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--fg-2)'
    }
  }, label), /*#__PURE__*/React.createElement("select", {
    value: value,
    onChange: onChange,
    style: {
      padding: '11px 14px',
      borderRadius: 'var(--radius-m)',
      border: '1px solid var(--border-2)',
      fontSize: 'var(--text-body)',
      color: 'var(--fg-1)',
      background: 'var(--white)',
      outline: 'none'
    }
  }, options.map(o => /*#__PURE__*/React.createElement("option", {
    key: o,
    value: o
  }, o))));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Footer.jsx
try { (() => {
function Footer() {
  const cols = [{
    h: 'Explore',
    items: ['Find a Trail', 'Maps & Guides', 'Trail Regions', 'Events']
  }, {
    h: 'Get Involved',
    items: ['Volunteer', 'Membership', 'Careers', 'Donate']
  }, {
    h: 'About',
    items: ['Our Mission', 'Board & Staff', 'Trail Walker Magazine', 'Contact']
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--pine-900)',
      color: 'var(--sage-200)',
      fontFamily: 'var(--font-body)',
      padding: '48px 32px 28px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 64,
      flexWrap: 'wrap',
      maxWidth: 1200,
      margin: '0 auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 220
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--paper-0)',
      fontFamily: 'var(--font-display)',
      fontWeight: 700,
      fontSize: 22
    }
  }, "OurHike"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 10,
      fontSize: 'var(--text-body-s)',
      lineHeight: 'var(--leading-relaxed)'
    }
  }, "600 Ramapo Valley Rd", /*#__PURE__*/React.createElement("br", null), "Mahwah, NJ 07430")), cols.map(c => /*#__PURE__*/React.createElement("div", {
    key: c.h
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--paper-0)',
      fontWeight: 'var(--weight-semibold)',
      fontSize: 'var(--text-body-s)',
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-wide)',
      marginBottom: 12
    }
  }, c.h), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, c.items.map(i => /*#__PURE__*/React.createElement("a", {
    key: i,
    href: "#",
    style: {
      color: 'var(--sage-200)',
      textDecoration: 'none',
      fontSize: 'var(--text-body-s)'
    }
  }, i)))))), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--pine-700)',
      marginTop: 36,
      paddingTop: 18,
      fontSize: 'var(--text-caption)',
      maxWidth: 1200,
      margin: '36px auto 0'
    }
  }, "\xA9 2026 OurHike."));
}
Object.assign(__ds_scope, { Footer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Footer.jsx", error: String((e && e.message) || e) }); }

// components/navigation/NavBar.jsx
try { (() => {
function NavBar({
  links = ['Trails', 'Get Involved', 'Shop', 'About'],
  active
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 32px',
      background: 'var(--pine-900)',
      fontFamily: 'var(--font-body)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/trail-blaze-logo.svg",
    style: {
      width: 8,
      height: 28,
      objectFit: 'contain'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--paper-0)',
      fontFamily: 'var(--font-display)',
      fontWeight: 700,
      fontSize: 20,
      letterSpacing: '-0.01em'
    }
  }, "OurHike")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 28
    }
  }, links.map(l => /*#__PURE__*/React.createElement("a", {
    key: l,
    href: "#",
    style: {
      color: l === active ? 'var(--blaze-yellow)' : 'var(--sage-200)',
      textDecoration: 'none',
      fontSize: 'var(--text-body-s)',
      fontWeight: 'var(--weight-semibold)',
      letterSpacing: 'var(--tracking-wide)',
      textTransform: 'uppercase'
    }
  }, l))), /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "secondary",
    size: "s"
  }, "Donate"));
}
Object.assign(__ds_scope, { NavBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/NavBar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/Homepage.jsx
try { (() => {
function Hero() {
  const NS = window.OurHikeDesignSystem_60cee1;
  const {
    Button
  } = NS;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'linear-gradient(180deg, var(--pine-800), var(--pine-900))',
      padding: '100px 32px 90px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      textAlign: 'center',
      gap: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--sage-200)',
      fontFamily: 'var(--font-body)',
      fontSize: 'var(--text-eyebrow)',
      letterSpacing: 'var(--tracking-eyebrow)',
      textTransform: 'uppercase',
      fontWeight: 600
    }
  }, "Est. 1920 \xB7 Volunteer-Powered"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--paper-0)',
      fontFamily: 'var(--font-display)',
      fontWeight: 700,
      fontSize: 'var(--text-display-xl)',
      lineHeight: 'var(--leading-tight)',
      maxWidth: 820
    }
  }, "Blaze your path. Hike your own hike."), /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--sage-200)',
      fontFamily: 'var(--font-body)',
      fontSize: 'var(--text-body-l)',
      maxWidth: 560,
      lineHeight: 'var(--leading-relaxed)'
    }
  }, "Connect with the communities that build, maintain, and protect 2,100+ miles of public trails across New York and New Jersey."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12,
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "l"
  }, "Find a Trail"), /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    size: "l",
    style: {
      color: 'var(--paper-0)',
      borderColor: 'var(--sage-200)'
    }
  }, "Become a Member")));
}
function TrailGrid() {
  const NS = window.OurHikeDesignSystem_60cee1;
  const {
    Card,
    Badge
  } = NS;
  const trails = [{
    park: 'Harriman State Park',
    name: 'Suffern-Bear Mountain Trail',
    meta: '7.2 mi · 4–5 hrs',
    tone: 'strenuous',
    label: 'Strenuous'
  }, {
    park: 'Ramapo Valley Reservation',
    name: 'Darlington Schoolhouse Loop',
    meta: '2.1 mi · 1 hr',
    tone: 'easy',
    label: 'Easy'
  }, {
    park: 'Norvin Green State Forest',
    name: 'Wyanokie High Point',
    meta: '4.8 mi · 3 hrs',
    tone: 'moderate',
    label: 'Moderate'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '56px 32px',
      background: 'var(--bg-page)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontSize: 'var(--text-display-s)',
      color: 'var(--fg-1)',
      marginBottom: 24
    }
  }, "Featured Trails"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3,1fr)',
      gap: 20
    }
  }, trails.map(t => /*#__PURE__*/React.createElement(Card, {
    key: t.name,
    image: /*#__PURE__*/React.createElement("div", {
      style: {
        width: '100%',
        height: '100%',
        background: 'linear-gradient(135deg,var(--sage-200),var(--moss-400))'
      }
    }),
    eyebrow: t.park,
    title: t.name,
    meta: t.meta,
    footer: /*#__PURE__*/React.createElement(Badge, {
      tone: t.tone
    }, t.label)
  })))));
}
function MembershipCallout() {
  const NS = window.OurHikeDesignSystem_60cee1;
  const {
    Callout,
    Button
  } = NS;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 32px 64px',
      background: 'var(--bg-page)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto'
    }
  }, /*#__PURE__*/React.createElement(Callout, {
    tone: "brand",
    title: "Support 2,100+ Miles of Trail",
    action: /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "m"
    }, "Support Them")
  }, "The organizations who maintain these trails take members and donations directly, on their own sites. OurHike takes no cut and holds no money.")));
}
function Homepage() {
  const NS = window.OurHikeDesignSystem_60cee1;
  const {
    NavBar,
    Footer
  } = NS;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-body)'
    }
  }, /*#__PURE__*/React.createElement(NavBar, {
    active: "Trails"
  }), /*#__PURE__*/React.createElement(Hero, null), /*#__PURE__*/React.createElement(TrailGrid, null), /*#__PURE__*/React.createElement(MembershipCallout, null), /*#__PURE__*/React.createElement(Footer, null));
}
window.Homepage = Homepage;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/Homepage.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Callout = __ds_scope.Callout;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Footer = __ds_scope.Footer;

__ds_ns.NavBar = __ds_scope.NavBar;

})();
