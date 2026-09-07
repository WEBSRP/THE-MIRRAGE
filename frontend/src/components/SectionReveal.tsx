import { useIntersectionObserver } from '../hooks/useIntersectionObserver';

interface SectionRevealProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}

/**
 * Wrapper component that reveals children with a fade-up animation
 * when they enter the viewport.
 */
export function SectionReveal({ children, className = '', delay = 0 }: SectionRevealProps) {
  const { ref, isVisible } = useIntersectionObserver({ threshold: 0.15 });

  return (
    <div
      ref={ref}
      className={`transition-all duration-1000 ease-out ${
        isVisible
          ? 'opacity-100 translate-y-0'
          : 'opacity-0 translate-y-8'
      } ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}
