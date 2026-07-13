import { Link } from "react-router-dom";

export type AiRecommendationChip = {
  emoji: string;
  label: string;
};

export type AiRecommendationCardVisual = {
  avatar: string;
  headline: string;
  subline: string;
  chips: AiRecommendationChip[];
};

type AiRecommendationCardProps = {
  to: string;
  title: string;
  saving: string;
  detail: string;
  visual: AiRecommendationCardVisual;
  tabIndex?: number;
};

export function AiRecommendationCard({
  to,
  title,
  saving,
  detail,
  visual,
  tabIndex,
}: AiRecommendationCardProps) {
  return (
    <Link className="prototype-home-ai-card" to={to} tabIndex={tabIndex}>
      <div className="prototype-home-ai-visual" aria-hidden="true">
        <div className="prototype-home-ai-chat-topline">
          <span className="prototype-home-ai-chat-avatar">{visual.avatar}</span>
          <div className="prototype-home-ai-chat-copy">
            <span className="prototype-home-ai-chat-bubble primary">
              {visual.headline}
            </span>
            <span className="prototype-home-ai-chat-bubble secondary">
              {visual.subline}
            </span>
          </div>
        </div>
        <div className="prototype-home-ai-action-dock">
          {visual.chips.map((chip) => (
            <span className="prototype-home-ai-dock-chip" key={chip.label}>
              <span className="prototype-home-ai-dock-emoji">{chip.emoji}</span>
              <span className="prototype-home-ai-dock-label">{chip.label}</span>
            </span>
          ))}
        </div>
      </div>
      <div className="prototype-home-ai-body">
        <strong>{title}</strong>
        <div className="prototype-home-ai-meta">
          <span className="prototype-home-ai-saving">{saving}</span>
          <span className="prototype-home-ai-detail">{detail}</span>
        </div>
      </div>
    </Link>
  );
}
