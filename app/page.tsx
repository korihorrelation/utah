import dynamic from 'next/dynamic';
import styles from './page.module.css';

const InteractiveUtahMap = dynamic(
  () => import('../components/InteractiveUtahMap'),
  { ssr: false }
);

export default function Home() {
  return (
    <main className={styles.page}>
      <section className={styles.header}>
        <div>
          <p className={styles.tag}>Utah County Election Map</p>
          <h1 className={styles.title}>Precinct vote trends with hover charts</h1>
          <p className={styles.description}>
            Explore Utah county ballot-area voting patterns by precinct or district. Hover over any shape to reveal election totals and a line chart across recent cycles.
          </p>
        </div>
      </section>
      <InteractiveUtahMap />
    </main>
  );
}
