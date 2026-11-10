"""Run an ngspice transient test derived from the exported S3 KiCad netlist."""
import csv
import html
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 's3_interface'
OUTPUT = PROJECT / 'simulation'


def topology():
    root = ET.parse(PROJECT / 'S3_interface.net.xml').getroot()
    pins = {}
    for net in root.findall('./nets/net'):
        for item in net.findall('node'):
            pins[(item.attrib['ref'], item.attrib['pin'])] = net.attrib['name']
    expected = {
        '/+5V_IN': [('J1','1'), ('F1','1')],
        '/+5V': [('F1','2'), ('C1','1'), ('SW1','1'), ('J2','1'), ('R4','1'), ('R5','1')],
        '/GND': [('J1','2'), ('J2','2'), ('Q1','3'), ('R3','2'), ('R6','2'), ('C2','2'), ('C3','2'), ('J3','2'), ('J4','2')],
        '/PERMIT_OK': [('SW1','2'), ('R1','1'), ('R6','1'), ('J2','6')],
        '/CLAMP_CMD': [('J2','3'), ('R2','1')],
        '/PART_N': [('J3','1'), ('J2','4'), ('R4','2'), ('C2','1')],
        '/COVER_N': [('J4','1'), ('J2','5'), ('R5','2'), ('C3','1')],
        '/CLAMP_COLLECTOR': [('Q1','1'), ('D1','1'), ('TP1','1')],
    }
    for name, references in expected.items():
        for reference in references:
            if pins[reference] != name:
                raise ValueError(f'Unexpected net at {reference}: {pins[reference]}')
    if pins[('D1','2')] != pins[('R1','2')]:
        raise ValueError('LED anode is not connected to R1')
    if not pins[('Q1','2')] == pins[('R2','2')] == pins[('R3','1')]:
        raise ValueError('Base network is inconsistent')
    aliases = {'/GND':'0', '/+5V_IN':'vin', '/+5V':'v5', '/PERMIT_OK':'permit_ok',
               '/CLAMP_CMD':'cmd', '/PART_N':'part_n', '/COVER_N':'cover_n',
               '/CLAMP_COLLECTOR':'collector', pins[('D1','2')]:'led_anode', pins[('Q1','2')]:'base'}
    values = {item.attrib['ref']: item.findtext('value') for item in root.findall('./components/comp')}
    return lambda ref, pin: aliases[pins[(ref, str(pin))]], values, expected


def deck(node, values):
    lines = ['S3 5V mock clamp and dry-contact input test',
             '* Generated from S3_interface.net.xml. Generic models, not manufacturer-calibrated.',
             'VIN vin 0 DC 5',
             '* F1 uses 1 ohm series resistance; fuse opening is not modeled.',
             f'RF1 {node("F1",1)} {node("F1",2)} 1']
    for ref in ('R1','R2','R3','R4','R5','R6','C1','C2','C3'):
        lines.append(f'{ref} {node(ref,1)} {node(ref,2)} {values[ref]}')
    lines += [f'D1 {node("D1",2)} {node("D1",1)} LED_DEMO',
              f'Q1 {node("Q1",1)} {node("Q1",2)} {node("Q1",3)} NPN_DEMO',
              f'SPERMIT {node("SW1",1)} {node("SW1",2)} permit_ctrl 0 CONTACT',
              f'SPART {node("J3",1)} {node("J3",2)} part_ctrl 0 CONTACT',
              f'SCOVER {node("J4",1)} {node("J4",2)} cover_ctrl 0 CONTACT',
              'VCMD cmd 0 PWL(0 0 1.999m 0 2m 5 17.999m 5 18m 0 24.999m 0 25m 5 40m 5)',
              'VPERMIT permit_ctrl 0 PWL(0 5 9.999m 5 10m 0 24.999m 0 25m 5 40m 5)',
              'VPART part_ctrl 0 PWL(0 0 4.999m 0 5m 5 14.999m 5 15m 0 40m 0)',
              'VCOVER cover_ctrl 0 PWL(0 0 7.999m 0 8m 5 19.999m 5 20m 0 40m 0)',
              '.model CONTACT SW(RON=1 ROFF=1e12 VT=2.5 VH=0.1)',
              '.model NPN_DEMO NPN(IS=1e-14 BF=200 VAF=100 CJE=10p CJC=4p TF=0.3n)',
              '.model LED_DEMO D(IS=1e-20 N=2 RS=5)',
              '.control', 'set noaskquit', 'set numdgt=12', 'set wr_singlescale', 'set wr_vecnames',
              'tran 2u 40m', 'let led_current=(v(permit_ok)-v(led_anode))/680',
              'let base_current=(v(cmd)-v(base))/4700',
              'wrdata waveforms.txt v(cmd) v(permit_ok) v(part_n) v(cover_n) v(collector) led_current base_current v(v5)',
              'quit', '.endc', '.end']
    return '\n'.join(lines) + '\n'


def sample(rows, time):
    return min(rows, key=lambda row: abs(row['time_s']-time))


def crossing(rows, voltage, after):
    filtered = [row for row in rows if row['time_s'] >= after]
    for left, right in zip(filtered, filtered[1:]):
        if left['part_v'] <= voltage < right['part_v']:
            fraction = (voltage-left['part_v'])/(right['part_v']-left['part_v'])
            return left['time_s']+fraction*(right['time_s']-left['time_s'])
    raise ValueError('Expected input transition was not found')


def plot(rows):
    width, height = 1100, 900
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#fbfcf8"/>']
    parts.append('<g font-family="Arial,sans-serif"><text x="70" y="30" font-size="20" fill="#244635">S3 transient simulation | ngspice | generic component models</text>')
    panels = [(['command_v','permit_v'],['Clamp command','Permit/load rail'],0,5.5,'V'),
              (['led_a'],['LED current'],0,.006,'mA'),
              (['part_v','cover_v'],['Part input (active low)','Cover input (active low)'],0,5.5,'V'),
              (['collector_v'],['Q1 collector'],0,5.5,'V')]
    colors = ['#23644f','#c07939']
    for index,(keys,labels,low,high,unit) in enumerate(panels):
        top = 80 + index*200
        for step in range(5):
            x = 80 + step*240
            parts.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top+140}" stroke="#e1e7db"/>')
            parts.append(f'<text x="{x-8}" y="{top+158}" font-size="11" fill="#75836d">{step*10} ms</text>')
        for step in range(3):
            y = top+140-step*70
            value = low+(high-low)*step/2
            shown = value*1000 if unit=='mA' else value
            parts.append(f'<line x1="80" y1="{y}" x2="1040" y2="{y}" stroke="#e1e7db"/><text x="10" y="{y+4}" font-size="11" fill="#75836d">{shown:.1f} {unit}</text>')
        for j,(key,label) in enumerate(zip(keys,labels)):
            points = []
            for row in rows[::max(1,len(rows)//2200)]:
                x = 80+row['time_s']/.04*960
                y = top+140-(row[key]-low)/(high-low)*140
                points.append(f'{x:.2f},{y:.2f}')
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[j]}" stroke-width="2"/>')
            parts.append(f'<text x="{80+j*340}" y="{top-14}" font-size="14" fill="{colors[j]}">{html.escape(label)}</text>')
    parts.append('</g></svg>')
    return ''.join(parts)


def main():
    OUTPUT.mkdir(exist_ok=True)
    subprocess.run(['docker','exec','energyline-kicad','kicad-cli','sch','export','netlist','--format','kicadxml','--output','/project/S3_interface.net.xml','/project/S3_interface.kicad_sch'],check=True,capture_output=True)
    node, values, nets = topology()
    (OUTPUT/'s3_transient.cir').write_text(deck(node,values))
    subprocess.run(['docker','exec','-w','/project/simulation','energyline-kicad','ngspice','-b','-o','ngspice.log','s3_transient.cir'],check=True,capture_output=True,text=True)
    fields = ['time_s','command_v','permit_v','part_v','cover_v','collector_v','led_a','base_a','supply_v']
    raw = (OUTPUT/'waveforms.txt').read_text().splitlines()
    rows = [dict(zip(fields,map(float,line.split()))) for line in raw[1:] if line.strip()]
    if not rows or any(len(line.split())!=len(fields) for line in raw[1:] if line.strip()):
        raise ValueError('Unexpected ngspice waveform format')
    with (OUTPUT/'waveforms.csv').open('w',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    off,on,inhibited,restored = [sample(rows,time) for time in (.001,.009,.012,.028)]
    rise = crossing(rows,4.5,.015)-crossing(rows,.5,.015)
    expected_rise = math.log(9)*10000*10e-9
    tests = [
        ('Command low keeps LED off', off['led_a'] < 1e-6, off['led_a'], 'A'),
        ('Command and permit high turn LED on', on['led_a'] > .001, on['led_a'], 'A'),
        ('Permit removal inhibits output while command stays high', inhibited['command_v']>4.5 and inhibited['led_a']<1e-6, inhibited['led_a'], 'A'),
        ('Restored permit and command turn LED on again', restored['led_a']>.001, restored['led_a'], 'A'),
        ('Open contacts read high', off['part_v']>3.5 and off['cover_v']>3.5, min(off['part_v'],off['cover_v']), 'V'),
        ('Part contact closure reads low', sample(rows,.007)['part_v']<1.5, sample(rows,.007)['part_v'], 'V'),
        ('Cover contact closure reads low', sample(rows,.009)['cover_v']<1.5, sample(rows,.009)['cover_v'], 'V'),
        ('Part release returns high', sample(rows,.016)['part_v']>3.5, sample(rows,.016)['part_v'], 'V'),
        ('Cover release returns high', sample(rows,.021)['cover_v']>3.5, sample(rows,.021)['cover_v'], 'V'),
        ('Q1 saturates under LED load', on['collector_v']<.3, on['collector_v'], 'V'),
        ('Fused supply stays above 4.9V for modeled load', on['supply_v']>4.9, on['supply_v'], 'V'),
        ('Input 10-90% rise agrees with 10k/10n RC within 10%', abs(rise-expected_rise)/expected_rise<.1, rise*1e6, 'us'),
    ]
    report = {'engine':'ngspice 46','analysis':'Transient, 0-40ms, maximum step 2us','schematic':'S3_interface.kicad_sch',
              'netlist':'S3_interface.net.xml','topology_checked_against_export':True,'samples':len(rows),
              'checks':[{'name':name,'passed':bool(passed),'value':value,'unit':unit} for name,passed,value,unit in tests],
              'passed':all(test[1] for test in tests),'led_on_ma':on['led_a']*1000,'led_inhibited_ua':inhibited['led_a']*1e6,
              'collector_on_v':on['collector_v'],'part_rise_10_90_us':rise*1e6,'expected_rc_rise_us':expected_rise*1e6,
              'models':'Generic NPN and red LED; BC547B manufacturer behavior is not calibrated',
              'limitations':['External controller represented by ideal 0/5V source; controller power draw omitted',
                             'Permit and dry contacts use ideal controlled switch models',
                             'F1 represented as 1 ohm; fuse opening not simulated',
                             'Input thresholds assumed 1.5/3.5V for this 5V demonstration',
                             'No mechanical switch bounce, EMC, ESD, component tolerance or thermal analysis',
                             'LED mock load only; no motor, solenoid or certified safety function']}
    (OUTPUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    graphic = plot(rows);(OUTPUT/'waveforms.svg').write_text(graphic)
    table = ''.join(f'<tr><td>{html.escape(name)}</td><td>{"PASS" if passed else "FAIL"}</td><td>{value:.6g} {unit}</td></tr>' for name,passed,value,unit in tests)
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>S3 circuit simulation</title><style>body{{font-family:Arial,sans-serif;background:#f4f5ef;color:#244635;max-width:1100px;margin:35px auto;padding:0 20px}}h1{{font-size:30px}}p,li{{line-height:1.7;font-size:14px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:12px;border-bottom:1px solid #d7e0cf;text-align:left}}.card{{background:white;padding:24px;border-radius:10px;margin:20px 0}}svg{{width:100%;height:auto}}a{{color:#23644f}}</style></head><body><h1>S3 circuit simulation</h1><p>ngspice transient analysis derived from the exported KiCad circuit netlist. Generic component models; no hardware validation.</p><div class="card"><b>{sum(test[1] for test in tests)}/{len(tests)} checks passed</b><p>LED on current: {report['led_on_ma']:.3f} mA. Permit removed, command still high: {report['led_inhibited_ua']:.6f} µA. Q1 collector when on: {report['collector_on_v']:.4f} V. Input 10-90% rise: {rise*1e6:.1f} µs.</p></div><div class="card">{graphic}</div><div class="card"><h2>Checks</h2><table><tr><th>Check</th><th>Result</th><th>Measured in simulation</th></tr>{table}</table></div><div class="card"><h2>Model limits</h2><ul>{''.join('<li>'+html.escape(item)+'</li>' for item in report['limitations'])}</ul><p>The RC network has a 100 µs nominal time constant. It has not been tested as a complete contact-debounce solution.</p><a href="http://localhost:3090">Open KiCad</a> · <a href="/">Experiment studio</a></div></body></html>'''
    (OUTPUT/'report.html').write_text(page)
    (ROOT.parent/'web/circuit_simulation.html').write_text(page)
    for name,passed,value,unit in tests:print(f'{"PASS" if passed else "FAIL"}: {name}: {value:.6g} {unit}')
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
