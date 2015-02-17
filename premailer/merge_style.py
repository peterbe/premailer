
import cssutils
import threading
import re


def csstext_to_pairs(csstext):
    """
        csstext_to_pairs takes css text and make it to list of tuple of key,value
    """
    # The lock is required to avoid ``cssutils`` concurrency issues documented in issue #65
    with csstext_to_pairs._lock:
        parsed = cssutils.css.CSSVariablesDeclaration(csstext)
        return [(key.strip(), parsed.getVariableValue(key).strip()) for key in sorted(parsed)]

csstext_to_pairs._lock = threading.RLock()

def merge_styles(inline_style, new_styles, classes):    
    """
        This will merge all new styles where the order is important
        The last one will override the first
        When that is done it will apply old inline style again
        
        Args:
            inline_style(str): the old inline style of the element if there is one
            new_styles: a list of new styles, each element should be a list of tuple
            classes: a list of classes which maps new_styles, important! 
            
        Returns:
            str: the final style
    """
    # building classes
    styles = {pc: {} for pc in set(classes)}
    # probably faster just override
    styles[''] = {}
    for i, style in enumerate(new_styles):
        for k, v in style:
            styles[classes[i]][k] = v
            
    # keep always the old inline style
    if inline_style:
        # inline should be a declaration list as I understand
        # ie property-name:property-value;...
        for k, v in csstext_to_pairs(inline_style):
            styles[''][k] = v
        
    normal_styles = []
    pseudo_styles = []
    for pseudoclass, kv in styles.items():
        if not kv:
            continue
        if pseudoclass:
            pseudo_styles.append('%s{%s}' % (pseudoclass ,'; '.join('%s:%s' % (k, v) for k, v in sorted(kv.items()))))
        else:
            normal_styles.append('; '.join('%s:%s' % (k, v) for k, v in sorted(kv.items())))
    
    if pseudo_styles:
        all_styles = (['{%s}' % ''.join(normal_styles)] + pseudo_styles) if normal_styles else pseudo_styles
    else:
        all_styles = normal_styles
        
    return ' '.join(all_styles).strip()

