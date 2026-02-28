"use client";

import { useEffect, useState } from "react";
import { getSecurityConfig } from "@/lib/admin";

/**
 * Classification banners displayed at the top and bottom of the viewport.
 * Color-coded per government standard:
 *   - green:  UNCLASSIFIED
 *   - blue:   CUI
 *   - orange: FOUO
 *   - red:    SECRET
 *   - yellow: TOP_SECRET
 */

interface BannerStyle {
  bg: string;
  color: string;
  label: string;
}

const BANNER_STYLES: Record<string, BannerStyle> = {
  UNCLASSIFIED: {
    bg: "#166534",
    color: "#4ade80",
    label: "UNCLASSIFIED",
  },
  CUI: {
    bg: "#1e3a5f",
    color: "#60a5fa",
    label: "CUI - CONTROLLED UNCLASSIFIED INFORMATION",
  },
  FOUO: {
    bg: "#7c2d12",
    color: "#fb923c",
    label: "FOR OFFICIAL USE ONLY",
  },
  SECRET: {
    bg: "#7f1d1d",
    color: "#f87171",
    label: "SECRET",
  },
  TOP_SECRET: {
    bg: "#78350f",
    color: "#fbbf24",
    label: "TOP SECRET",
  },
};

function Banner({
  position,
  style,
}: {
  position: "top" | "bottom";
  style: BannerStyle;
}) {
  return (
    <div
      style={{
        position: "fixed",
        [position]: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        backgroundColor: style.bg,
        color: style.color,
        textAlign: "center",
        fontSize: "12px",
        fontWeight: 700,
        letterSpacing: "0.1em",
        padding: "3px 0",
        userSelect: "none",
      }}
      role="banner"
      aria-label={`Classification: ${style.label}`}
    >
      {style.label}
    </div>
  );
}

export default function ClassificationBanner() {
  const [level, setLevel] = useState<string>("UNCLASSIFIED");

  useEffect(() => {
    // Try to read the highest classification from the security config
    getSecurityConfig()
      .then((cfg) => {
        if (cfg.classification_levels && cfg.classification_levels.length > 0) {
          // Use the highest configured level as the system banner
          const hierarchy = [
            "UNCLASSIFIED",
            "CUI",
            "FOUO",
            "SECRET",
            "TOP_SECRET",
          ];
          const highest = cfg.classification_levels.reduce((max, l) => {
            const li = hierarchy.indexOf(l);
            const mi = hierarchy.indexOf(max);
            return li > mi ? l : max;
          }, "UNCLASSIFIED");
          setLevel(highest);
        }
      })
      .catch(() => {
        // If not authenticated or API unavailable, stay UNCLASSIFIED
      });
  }, []);

  const style = BANNER_STYLES[level] || BANNER_STYLES["UNCLASSIFIED"];

  return (
    <>
      <Banner position="top" style={style} />
      <Banner position="bottom" style={style} />
      {/* Spacers so content doesn't hide behind fixed banners */}
      <div style={{ height: "22px" }} />
    </>
  );
}
