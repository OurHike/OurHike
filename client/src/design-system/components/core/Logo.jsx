import React from 'react';

// Reconstructs the chosen "4a — Dual-Tone Horizontal Lockup" logo mark exactly
// (see the Logo Ideas design project, direction 4a): a rounded-square icon split
// diagonally into forest/stone, a white torn-edge "trail blaze" capsule on top,
// paired with the OurHike wordmark. All proportions scale from the 96px
// reference size the source design specifies as exact/final.
const REF_SIZE = 96;
const WORDMARK_SIZE = 30;
const LOCKUP_GAP = 16;

export function Logo({ size = REF_SIZE, iconOnly = false, style }) {
  const scale = size / REF_SIZE;
  const radius = 20 * scale;
  const gap = LOCKUP_GAP * scale;

  const icon = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      role="img"
      aria-label={iconOnly ? 'OurHike' : undefined}
      aria-hidden={iconOnly ? undefined : true}
      style={{ borderRadius: radius, overflow: 'hidden', flexShrink: 0 }}
    >
      <defs>
        <linearGradient id="ourhike-icon-split" x1="0" y1="0" x2="1" y2="1">
          <stop offset="50%" stopColor="var(--forest-600)" />
          <stop offset="50%" stopColor="var(--stone-700)" />
        </linearGradient>
        <clipPath id="ourhike-icon-round">
          <rect width="96" height="96" rx="20" />
        </clipPath>
        <filter id="ourhike-blaze-jag" x="-40%" y="-15%" width="180%" height="130%">
          <feTurbulence type="fractalNoise" baseFrequency="0.03 0.09" numOctaves="2" seed="7" result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale="10" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
      <g clipPath="url(#ourhike-icon-round)">
        <rect width="96" height="96" fill="url(#ourhike-icon-split)" />
        <svg x="31" y="8" width="34" height="80" viewBox="0 0 40 100">
          <rect x="10" y="8" width="20" height="84" rx="10" fill="var(--white)" filter="url(#ourhike-blaze-jag)" />
        </svg>
      </g>
    </svg>
  );

  if (iconOnly) return icon;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap,
        ...style,
      }}
    >
      {icon}
      <span
        style={{
          fontFamily: 'var(--font-display, Public Sans, sans-serif)',
          fontWeight: 800,
          fontSize: WORDMARK_SIZE * scale,
          letterSpacing: '-0.02em',
          color: 'var(--stone-900)',
        }}
      >
        OurHike
      </span>
    </span>
  );
}
