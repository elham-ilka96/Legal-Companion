import { useState } from "react";
import "./BottomNav.css";

function NavIcon({ name, className = "" }) {
  const common = {
    className,
    xmlns: "http://www.w3.org/2000/svg",
    width: "22",
    height: "22",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };

  if (name === "home") {
    return (
      <svg {...common}>
        <path d="M3 10.5 12 3l9 7.5" />
        <path d="M5 9.5V21h14V9.5" />
      </svg>
    );
  }

  if (name === "cases") {
    return (
      <svg {...common}>
        <rect x="2" y="7" width="20" height="14" rx="2" />
        <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        <path d="M2 12h20" />
      </svg>
    );
  }

  if (name === "notices") {
    return (
      <svg {...common}>
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    );
  }

  if (name === "account") {
    return (
      <svg {...common}>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
      </svg>
    );
  }

  return null;
}

export default function BottomNav({ active = "home", onChange = () => {} }) {
  const items = [
    { key: "home", label: "خانه" },
    { key: "cases", label: "پرونده‌ها" },
    { key: "notices", label: "ابلاغیه‌ها" },
    { key: "account", label: "حساب من" },
  ];

  return (
    <nav className="bottom-nav" aria-label="ناوبری پایین">
      {items.map((item) => {
        const isActive = active === item.key;
        return (
          <button
            key={item.key}
            type="button"
            className={`bottom-nav-item ${isActive ? "active" : ""}`}
            onClick={() => onChange(item.key)}
            aria-current={isActive ? "page" : undefined}
          >
            <NavIcon name={item.key} className="bottom-nav-icon" />
            <span className="bottom-nav-label">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}